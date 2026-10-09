"""Admin routes: /admin (list), /admin/reponses/{id} (review), /admin/login.

Every response goes through `_html` or `_redirect`, which add the security headers; every
handler but the login starts with `_guard`.
"""

import logging
import re

from fastapi import APIRouter, Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from admin import auth, pages
from app.core.config import settings
from app.core.security import rate_limit_admin_login
from journal import review

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
    "Referrer-Policy": "no-referrer",
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


@router.get("/")
def entries(
    request: Request,
    statut: str = "",
    issue: str = "",
    canal: str = "",
    q: str = "",
    page: int = 1,
) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    page = max(page, 1)
    q = q.strip()[:100]
    rows, total = review.list_entries(
        review=statut or None, route=issue or None, channel=canal or None, text=q or None, page=page
    )
    return _html(
        pages.entries_list(
            rows, total, review=statut, route=issue, channel=canal, text=q, page=page
        )
    )


@router.get("/reponses/{entry_id}")
def entry(request: Request, entry_id: int) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    found = review.get_entry(entry_id)
    if found is None:
        return _html(pages.not_found(), 404)
    return _html(pages.entry_detail(found))


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
        return _html(pages.entry_detail(found, "Choisissez un classement."), 400)
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
