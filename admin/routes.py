"""Admin routes: /admin (list), /admin/reponses/{id} (review), /admin/synthese (summary),
/admin/sans-reponse (questions left without an answer, by theme), /admin/login.

Every response goes through `_html` or `_redirect`, which add the security headers; every
handler but the login starts with `_guard`.
"""

import logging
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from admin import auth, pages
from app.core.config import settings
from app.core.security import rate_limit_admin_login
from graph.nodes.grade import GRADE_THRESHOLD
from journal import review, stats, themes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)


def mount_admin(app: FastAPI) -> bool:
    """Add the admin pages, unless ADMIN_PASSWORD is empty (they are then not served at all).

    Call it before mount_chat: Chainlit, mounted on /, answers every path nothing else does."""
    if not settings.admin_password:
        logger.info("ADMIN_PASSWORD is not set: the /admin pages are disabled")
        return False
    app.include_router(router)
    return True


_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "X-Frame-Options": "DENY",
    # Not "no-referrer": with it browsers send "Origin: null" on the forms of the page itself,
    # which the CSRF check (admin/auth.py::same_origin) refuses. Nothing leaves the site anyway.
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
}
_QUESTION_ID = re.compile(r"^q\d{1,4}$")


def _html(content: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(content, status_code=status, headers=_HEADERS)


def _redirect(url: str) -> RedirectResponse:
    # 303: a POST is answered by a GET of the target
    return RedirectResponse(url, status_code=303, headers=_HEADERS)


def _guard(request: Request) -> Response | None:
    """The response to send instead of the page when the request is not allowed, else None."""
    if not auth.is_authenticated(request, settings.admin_password):
        return _redirect("/admin/login")
    if request.method == "POST" and not auth.same_origin(request):
        return _html(pages.layout("Refusé", "<p>Origine de la requête refusée.</p>"), 403)
    return None


@router.get("/login")
def login_page(request: Request) -> Response:
    if auth.is_authenticated(request, settings.admin_password):
        return _redirect("/admin/")
    return _html(pages.login_form())


@router.post("/login", dependencies=[Depends(rate_limit_admin_login)])
def login(request: Request, password: str = Form("")) -> Response:
    if not auth.same_origin(request):
        return _html(pages.login_form("Origine de la requête refusée."), 403)
    if not auth.check_password(password, settings.admin_password):
        return _html(pages.login_form("Mot de passe incorrect."), 401)
    response = _redirect("/admin/")
    response.set_cookie(
        auth.COOKIE,
        auth.make_token(settings.admin_password),
        max_age=auth.SESSION_TTL_S,
        path="/admin",
        httponly=True,
        secure=auth.cookie_is_secure(request),
        samesite="strict",
    )
    return response


@router.post("/logout")
def logout(request: Request) -> Response:
    if not auth.same_origin(request):
        return _html(pages.layout("Refusé", "<p>Origine de la requête refusée.</p>"), 403)
    response = _redirect("/admin/login")
    response.delete_cookie(auth.COOKIE, path="/admin")
    return response


@router.get("")
def without_slash() -> Response:
    """/admin as typed in the address bar. Without this route nothing matches it, and the
    chat (Chainlit, mounted on /) answers in place of the redirect to /admin/ that FastAPI
    would otherwise make."""
    return _redirect("/admin/")


@router.get("/")
def entries(
    request: Request,
    statut: str = "",
    issue: str = "",
    canal: str = "",
    avis: str = "",
    manque: str = "",
    q: str = "",
    page: int = 1,
) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    page = max(page, 1)
    q = q.strip()[:100]
    avis = avis if avis in review.FEEDBACK_FILTERS else ""
    manque = manque if manque in pages.GAP_CHOICES else ""
    rows, total = review.list_entries(
        review=statut or None,
        route=issue or None,
        channel=canal or None,
        text=q or None,
        feedback=avis or None,
        gap=manque or None,
        page=page,
    )
    return _html(
        pages.entries_list(
            rows,
            total,
            review=statut,
            route=issue,
            channel=canal,
            text=q,
            page=page,
            feedback=avis,
            gap=manque,
            unreviewed_negative=review.count_unreviewed_negative(),
        )
    )


@router.get("/synthese")
def summary(request: Request, periode: str = "") -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    return _html(pages.stats_page(stats.summary(periode), GRADE_THRESHOLD))


def _entry_page(
    found: dict, error: str | None = None, theme_error: str | None = None, status: int = 200
) -> Response:
    return _html(pages.entry_detail(found, error, themes.choices(), theme_error), status)


@router.get("/reponses/{entry_id}")
def entry(request: Request, entry_id: int) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    found = review.get_entry(entry_id)
    if found is None:
        return _html(pages.not_found(), 404)
    return _entry_page(found)


@router.post("/reponses/{entry_id}")
def classify(
    request: Request, entry_id: int, label: str = Form(""), note: str = Form("")
) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    found = review.get_entry(entry_id)
    if found is None:
        return _html(pages.not_found(), 404)
    if label not in review.REVIEW_LABELS:
        return _entry_page(found, "Choisissez un classement.", status=400)
    review.review(entry_id, label, note)
    following = review.next_unreviewed(entry_id)
    return _redirect(f"/admin/reponses/{following}" if following else "/admin/")


@router.get("/reponses/{entry_id}/yaml")
def excerpt(request: Request, entry_id: int) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    found = review.get_entry(entry_id)
    if found is None:
        return _html(pages.not_found(), 404)
    question_id = found["promoted_as"] or review.next_question_id()
    return _html(
        pages.yaml_page(
            entry_id, question_id, review.yaml_excerpt(found, question_id), found["promoted_as"]
        )
    )


@router.post("/reponses/{entry_id}/promotion")
def promote(request: Request, entry_id: int, question_id: str = Form("")) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    if not _QUESTION_ID.match(question_id) or not review.mark_promoted(entry_id, question_id):
        return _html(pages.not_found(), 404)
    return _redirect(f"/admin/reponses/{entry_id}")


# --- Questions left without an answer, by theme (#20) --------------------------------------


@router.get("/sans-reponse")
def unanswered(
    request: Request,
    periode: str = "",
    resultat: str = "",
    questions: int = 0,
    nouveaux: int = 0,
) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    period = periode if periode in stats.PERIODS else ""
    total, loose = themes.unthemed(period)
    return _html(
        pages.themes_page(
            themes.list_themes(period),
            total,
            loose,
            themes.pending_counts(),
            period,
            pages.grouping_message(resultat, max(questions, 0), max(nouveaux, 0)),
        )
    )


@router.post("/sans-reponse/regrouper")
def regroup(request: Request) -> Response:
    """One call to the LLM: the button says so. The result travels in the query of the
    redirect (numbers and a fixed code only), so that a reload does not group again."""
    if (denied := _guard(request)) is not None:
        return denied
    result = themes.group_pending()
    query = {
        "resultat": result.error or "ok",
        "questions": result.grouped,
        "nouveaux": len(result.new_themes),
    }
    return _redirect(f"/admin/sans-reponse?{urlencode(query)}")


def _theme_page(found: dict, error: str | None = None, status: int = 200) -> Response:
    hits: list[dict] = []
    search_error = None
    if found["example"]:
        try:
            hits = themes.current_search(found["example"])
        except Exception:
            logger.exception("The search of the theme page failed")
            search_error = (
                "La recherche ne répond pas (Qdrant ou le modèle d'embedding) : réessayez plus "
                "tard."
            )
    return _html(
        pages.theme_page(found, themes.choices(), hits, search_error, GRADE_THRESHOLD, error),
        status,
    )


@router.get("/sans-reponse/{theme_id}")
def theme(request: Request, theme_id: int) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    found = themes.get_theme(theme_id)
    if found is None:
        return _html(pages.not_found(), 404)
    return _theme_page(found)


@router.post("/sans-reponse/{theme_id}/nom")
def rename(request: Request, theme_id: int, nom: str = Form("")) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    problem = themes.rename(theme_id, nom[:200])
    found = themes.get_theme(theme_id)
    if found is None:
        return _html(pages.not_found(), 404)
    if problem:
        return _theme_page(found, problem, 400)
    return _redirect(f"/admin/sans-reponse/{theme_id}")


@router.post("/sans-reponse/{theme_id}/cause")
def cause(request: Request, theme_id: int, cause: str = Form(""), note: str = Form("")) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    found = themes.get_theme(theme_id)
    if found is None:
        return _html(pages.not_found(), 404)
    if cause and cause not in themes.CAUSES:
        return _theme_page(found, "Choisissez une cause.", 400)
    themes.set_cause(theme_id, cause or None, note)
    return _redirect(f"/admin/sans-reponse/{theme_id}")


@router.post("/sans-reponse/{theme_id}/fusion")
def merge(request: Request, theme_id: int, cible: str = Form("")) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    found = themes.get_theme(theme_id)
    if found is None:
        return _html(pages.not_found(), 404)
    target = int(cible) if cible.isdigit() else 0
    if not themes.merge(theme_id, target):
        return _theme_page(found, "Choisissez un autre thème.", 400)
    return _redirect(f"/admin/sans-reponse/{target}")


@router.post("/reponses/{entry_id}/theme")
def move(
    request: Request,
    entry_id: int,
    theme: str = Form(""),
    nouveau: str = Form(""),
    retour: str = Form(""),
) -> Response:
    """Move a question to a theme, a new one or none. `retour` is the id of the theme page
    the form was on (only a number: no redirect anywhere else)."""
    if (denied := _guard(request)) is not None:
        return denied
    found = review.get_entry(entry_id)
    if found is None:
        return _html(pages.not_found(), 404)
    if theme and not theme.isdigit():
        return _entry_page(found, theme_error="Thème introuvable.", status=400)
    problem = themes.move(entry_id, int(theme) if theme else None, nouveau[:200])
    if problem:
        return _entry_page(found, theme_error=problem, status=400)
    if retour.isdigit() and themes.get_theme(int(retour)) is not None:
        return _redirect(f"/admin/sans-reponse/{int(retour)}")
    return _redirect(f"/admin/reponses/{entry_id}")
