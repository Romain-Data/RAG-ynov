"""Tests for the admin pages that review the answer journal (no LLM)."""

import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from admin import auth, pages
from admin import dashboard as admin_dashboard
from admin.routes import mount_admin
from app import main
from app.core.config import settings
from app.core.security import add_security_middleware, limiter
from chat.db import db, init_db
from eval import dashboard as eval_dashboard
from eval import results as eval_results
from journal import gaps, report, review, stats, store, themes

# Generated for each run: no password-like literal in the repository
PASSWORD = secrets.token_urlsafe(24)
WRONG_PASSWORD = secrets.token_urlsafe(24)
SOURCES = [
    {
        "source": "bts-sio.html",
        "section": "Tarifs",
        "score": 0.71,
        "title": "BTS SIO",
        "url": "https://www.ynov.com/formations/bts-sio",
    },
    {"source": "evil.html", "section": None, "score": 0.5, "url": "javascript:alert(1)"},
]
RETRIEVED = [
    {"source": "bts-sio.html", "section": "Tarifs", "page": None, "score": 0.71},
    {"source": "bts-sio.html", "section": "Infos clés", "page": None, "score": 0.4},
]


@pytest.fixture(autouse=True)
def journal_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "chat.db"))
    monkeypatch.setattr(settings, "admin_password", PASSWORD)
    limiter.reset()
    init_db()


@pytest.fixture
def client() -> TestClient:
    """A client of an app with only the admin pages, over https (the cookie is Secure)."""
    app = FastAPI()
    add_security_middleware(app)
    assert mount_admin(app)
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def signed_in(client) -> TestClient:
    resp = client.post("/admin/login", data={"password": PASSWORD})
    assert resp.status_code == 303
    return client


def add(question="Combien coûte le BTS SIO ?", **kwargs) -> int:
    result = {
        "answer": "Environ 7 000 € par an [Source 1].",
        "grade": "ok",
        "sources": SOURCES,
        "retrieved": RETRIEVED,
        "llm_model": "mistral-medium-2508",
        "tokens_in": 1200,
        "tokens_out": 80,
    }
    result.update(kwargs.pop("result", {}))
    if "rewritten" in kwargs:  # a field of the graph state, not an argument of record()
        result["rewritten"] = kwargs.pop("rewritten")
    store.record(channel=kwargs.pop("channel", "chat"), question=question, result=result, **kwargs)
    with db() as conn:
        return conn.execute("SELECT MAX(id) FROM answer_log").fetchone()[0]


class TestAuthentication:
    def test_pages_redirect_to_the_login_without_a_cookie(self, client):
        for path in ("/admin/", "/admin/reponses/1", "/admin/reponses/1/yaml"):
            resp = client.get(path)
            assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"

    def test_posts_redirect_to_the_login_without_a_cookie(self, client):
        entry_id = add()
        for path in (f"/admin/reponses/{entry_id}", f"/admin/reponses/{entry_id}/promotion"):
            resp = client.post(path, data={"label": "bonne", "question_id": "q35"})
            assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"
        assert review.get_entry(entry_id)["review_label"] is None

    def test_wrong_password(self, client):
        resp = client.post("/admin/login", data={"password": WRONG_PASSWORD})
        assert resp.status_code == 401 and "incorrect" in resp.text
        assert auth.COOKIE not in resp.cookies

    def test_empty_password(self, client):
        assert client.post("/admin/login", data={}).status_code == 401

    def test_login_sets_a_strict_session_cookie(self, client):
        resp = client.post("/admin/login", data={"password": PASSWORD})
        cookie = resp.headers["set-cookie"].lower()
        assert resp.status_code == 303 and resp.headers["location"] == "/admin/"
        for flag in ("httponly", "secure", "samesite=strict", "path=/admin", "max-age=28800"):
            assert flag in cookie
        assert client.get("/admin/").status_code == 200

    def test_cookie_is_not_secure_on_plain_localhost(self):
        app = FastAPI()
        add_security_middleware(app)
        mount_admin(app)
        local = TestClient(app, base_url="http://localhost", follow_redirects=False)
        resp = local.post("/admin/login", data={"password": PASSWORD})
        assert "secure" not in resp.headers["set-cookie"].lower()

    def test_forged_cookie(self, client):
        client.cookies.set(auth.COOKIE, "9999999999.deadbeef", path="/admin")
        assert client.get("/admin/").status_code == 303

    def test_expired_cookie(self, client):
        token = auth.make_token(PASSWORD, now=time.time() - auth.SESSION_TTL_S - 10)
        client.cookies.set(auth.COOKIE, token, path="/admin")
        assert client.get("/admin/").status_code == 303

    def test_cookie_signed_with_another_password(self, client):
        client.cookies.set(auth.COOKIE, auth.make_token(WRONG_PASSWORD), path="/admin")
        assert client.get("/admin/").status_code == 303

    def test_changing_the_password_logs_everyone_out(self, signed_in, monkeypatch):
        monkeypatch.setattr(settings, "admin_password", PASSWORD + "-changed")
        assert signed_in.get("/admin/").status_code == 303

    @pytest.mark.parametrize("token", [None, "", "abc", "12.", ".sig", "x.y", "-5.sig"])
    def test_malformed_tokens(self, token):
        assert not auth.verify_token(PASSWORD, token)

    def test_logout(self, signed_in):
        resp = signed_in.post("/admin/logout")
        assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"
        assert signed_in.get("/admin/").status_code == 303

    def test_login_attempts_are_limited(self, client):
        codes = [
            client.post("/admin/login", data={"password": WRONG_PASSWORD}).status_code
            for _ in range(settings.rate_limit_admin_login + 2)
        ]
        assert codes[0] == 401 and codes[-1] == 429
        assert client.post("/admin/login", data={"password": PASSWORD}).status_code == 429

    def test_not_mounted_without_a_password(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_password", "")
        app = FastAPI()
        assert mount_admin(app) is False
        assert TestClient(app).get("/admin/login").status_code == 404

    def test_the_main_app_mounts_it_before_the_chat(self):
        # Chainlit, mounted on /, answers every path declared after it
        source = Path(main.__file__).read_text(encoding="utf-8")
        assert source.index("mount_admin(app)") < source.index("mount_chat(app)")


def test_admin_without_a_slash_is_not_answered_by_the_chat():
    """Chainlit is mounted on / and answers every path nothing else matches: /admin (typed
    without the final slash) used to show the chat login instead of the admin pages."""
    catch_all = Starlette(
        routes=[Route("/{path:path}", lambda _request: PlainTextResponse("chat"))]
    )
    app = FastAPI()
    assert mount_admin(app)
    app.mount("/", catch_all)  # after the admin routes, like mount_chat in app/main.py
    client = TestClient(app, base_url="https://testserver", follow_redirects=False)

    resp = client.get("/admin")
    assert resp.status_code == 303 and resp.headers["location"] == "/admin/"
    assert client.get("/admin/").headers["location"] == "/admin/login"
    assert client.get("/autre").text == "chat"  # the catch-all is really there


class TestOrigin:
    def test_foreign_origin_is_refused_on_a_post(self, signed_in):
        entry_id = add()
        resp = signed_in.post(
            f"/admin/reponses/{entry_id}",
            data={"label": "bonne"},
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403
        assert review.get_entry(entry_id)["review_label"] is None

    def test_pages_let_browsers_send_their_origin_on_forms(self, client):
        """ "Referrer-Policy: no-referrer" makes browsers send "Origin: null" on a form posted
        to the same site, which is refused above: the login could never succeed."""
        policy = client.get("/admin/login").headers["referrer-policy"]
        assert policy in {"same-origin", "strict-origin-when-cross-origin"}

    def test_null_origin_is_refused(self, signed_in):
        resp = signed_in.post("/admin/logout", headers={"Origin": "null"})
        assert resp.status_code == 403

    def test_foreign_origin_is_refused_at_the_login(self, client):
        resp = client.post(
            "/admin/login", data={"password": PASSWORD}, headers={"Origin": "https://evil.example"}
        )
        assert resp.status_code == 403 and auth.COOKIE not in resp.cookies

    def test_same_origin_is_accepted(self, signed_in):
        entry_id = add()
        resp = signed_in.post(
            f"/admin/reponses/{entry_id}",
            data={"label": "bonne"},
            headers={"Origin": "https://testserver"},
        )
        assert resp.status_code == 303


class TestHeaders:
    @pytest.mark.parametrize("path", ["/admin/login", "/admin/", "/admin/reponses/999"])
    def test_security_headers(self, signed_in, path):
        headers = signed_in.get(path).headers
        assert headers["cache-control"] == "no-store"
        assert "noindex" in headers["x-robots-tag"]
        assert headers["x-frame-options"] == "DENY"
        csp = headers["content-security-policy"]
        assert "script" not in csp.replace("scripts", "") and "default-src 'none'" in csp

    def test_redirects_carry_them_too(self, client):
        assert client.get("/admin/").headers["cache-control"] == "no-store"


class TestList:
    def test_lists_the_newest_first(self, signed_in):
        add("Première question")
        add("Deuxième question")
        text = signed_in.get("/admin/").text
        assert text.index("Deuxième question") < text.index("Première question")
        assert "2 réponse(s)" in text and "Générée" in text and "0,71" in text

    def test_content_is_escaped(self, signed_in):
        entry_id = add("<script>alert(1)</script>", result={"answer": "<img src=x onerror=y>"})
        listing = signed_in.get("/admin/").text
        assert "<script>alert(1)" not in listing and "&lt;script&gt;alert(1)" in listing
        detail = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert "<script>alert(1)" not in detail and "<img src=x" not in detail
        assert "&lt;img src=x onerror=y&gt;" in detail

    def test_filter_text_is_escaped_in_the_form(self, signed_in):
        text = signed_in.get("/admin/", params={"q": '"><script>x</script>'}).text
        assert "<script>x" not in text

    def test_filters(self, signed_in):
        reviewed = add("Question revue")
        add("Question à revoir")
        add("Il fait beau ?", result={"grade": "refuse", "retrieved": [], "sources": []})
        add("Question par API", channel="api")
        review.review(reviewed, "fausse")

        def shown(**params) -> str:
            return signed_in.get("/admin/", params=params).text

        assert "Question revue" not in shown(statut="unreviewed")
        assert "Question à revoir" in shown(statut="unreviewed")
        only_false = shown(statut="fausse")
        assert "Question revue" in only_false and "Question à revoir" not in only_false
        refused = shown(issue="refuse")
        assert "Il fait beau" in refused and "Question à revoir" not in refused
        via_api = shown(canal="api")
        assert "Question par API" in via_api and "Question à revoir" not in via_api
        assert "Aucune réponse" in shown(statut="inconnu")

    def test_text_search_takes_wildcards_literally(self, signed_in):
        add("Remise de 100% sur les frais")
        add("Remise de 1000 euros")
        found = signed_in.get("/admin/", params={"q": "100%"}).text
        assert "Remise de 100%" in found and "Remise de 1000" not in found
        assert "Aucune réponse" in signed_in.get("/admin/", params={"q": "_"}).text

    def test_search_covers_the_answer(self, signed_in):
        add("Q1", result={"answer": "La réponse mentionne Strasbourg"})
        add("Q2")
        text = signed_in.get("/admin/", params={"q": "strasbourg"}).text
        assert "Q1" in text and "Q2" not in text

    def test_pagination(self, signed_in):
        for number in range(review.PAGE_SIZE + 5):
            add(f"Question numéro {number}")
        first = signed_in.get("/admin/").text
        assert f"Question numéro {review.PAGE_SIZE + 4}" in first
        assert "Question numéro 0<" not in first and "Suivantes" in first
        assert "Précédentes" not in first
        second = signed_in.get("/admin/", params={"page": 2}).text
        assert "Question numéro 0<" in second and "Précédentes" in second
        assert "Suivantes" not in second

    def test_pager_links_keep_the_filters(self, signed_in):
        for number in range(review.PAGE_SIZE + 1):
            add(f"Question {number}")
        text = signed_in.get("/admin/", params={"statut": "unreviewed", "q": "Question"}).text
        assert "statut=unreviewed" in text and "q=Question" in text and "page=2" in text

    def test_page_out_of_range_is_empty(self, signed_in):
        add()
        assert "Aucune réponse" in signed_in.get("/admin/", params={"page": 9}).text
        assert signed_in.get("/admin/", params={"page": -3}).status_code == 200


class TestDetail:
    def test_shows_what_the_journal_holds(self, signed_in):
        entry_id = add(latency_ms=1234, rewritten="Combien coûte le BTS SIO à Lyon ?")
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        for expected in (
            "Combien coûte le BTS SIO ?",
            "Combien coûte le BTS SIO à Lyon ?",
            "Environ 7 000 €",
            "mistral-medium-2508",
            settings.mammouth_chat_model,
            "1200 → 80",
            "1234 ms",
            settings.qdrant_collection_name,
            "Infos clés",
            "seuil 0,47",
        ):
            assert expected in text

    def test_threshold_is_the_one_of_the_entry(self, signed_in):
        entry_id = add()
        with db() as conn:
            conn.execute("UPDATE answer_log SET threshold = 0.5")
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert "seuil 0,50" in text

    def test_only_http_links_are_clickable(self, signed_in):
        entry_id = add()
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert 'href="https://www.ynov.com/formations/bts-sio"' in text
        assert "javascript:" not in text.replace("evil.html", "")
        assert 'href="javascript' not in text

    def test_an_error_entry(self, signed_in):
        entry_id = add(result={"grade": "ok", "retrieved": [], "answer": ""}, error="LLMError: 429")
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert "LLMError: 429" in text and "Erreur" in text

    def test_unknown_entry(self, signed_in):
        resp = signed_in.get("/admin/reponses/999")
        assert resp.status_code == 404
        assert signed_in.get("/admin/reponses/abc").status_code == 422


class TestReview:
    def test_classify_and_go_to_the_next_unreviewed(self, signed_in):
        older = add("Plus ancienne")
        newer = add("Plus récente")
        resp = signed_in.post(
            f"/admin/reponses/{newer}", data={"label": "partielle", "note": "Manque le prix"}
        )
        assert resp.status_code == 303 and resp.headers["location"] == f"/admin/reponses/{older}"
        entry = review.get_entry(newer)
        assert entry["review_label"] == "partielle" and entry["review_note"] == "Manque le prix"
        assert entry["reviewed_at"]
        # the last one: back to the list
        resp = signed_in.post(f"/admin/reponses/{older}", data={"label": "bonne"})
        assert resp.headers["location"] == "/admin/"

    def test_a_classification_can_be_changed(self, signed_in):
        entry_id = add()
        signed_in.post(f"/admin/reponses/{entry_id}", data={"label": "fausse"})
        signed_in.post(f"/admin/reponses/{entry_id}", data={"label": "bonne", "note": ""})
        entry = review.get_entry(entry_id)
        assert entry["review_label"] == "bonne" and entry["review_note"] is None

    @pytest.mark.parametrize("label", ["", "excellente", "BONNE", "bonne'; DROP TABLE x;--"])
    def test_invalid_labels_are_refused(self, signed_in, label):
        entry_id = add()
        resp = signed_in.post(f"/admin/reponses/{entry_id}", data={"label": label})
        assert resp.status_code == 400 and "Choisissez" in resp.text
        assert review.get_entry(entry_id)["review_label"] is None

    def test_review_of_an_unknown_entry(self, signed_in):
        assert signed_in.post("/admin/reponses/999", data={"label": "bonne"}).status_code == 404

    def test_the_note_is_capped(self, signed_in):
        entry_id = add()
        signed_in.post(f"/admin/reponses/{entry_id}", data={"label": "bonne", "note": "x" * 5000})
        assert len(review.get_entry(entry_id)["review_note"]) == review.MAX_NOTE

    def test_the_detail_page_offers_the_labels_and_the_saved_choice(self, signed_in):
        entry_id = add()
        review.review(entry_id, "fausse", "Mauvais prix")
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        for value in review.REVIEW_LABELS:
            assert f'value="{value}"' in text
        assert 'value="fausse" required checked' in text and "Mauvais prix" in text


class TestPromotion:
    def test_excerpt_is_valid_yaml_with_the_next_id(self, signed_in):
        entry_id = add()
        text = signed_in.get(f"/admin/reponses/{entry_id}/yaml").text
        next_id = review.next_question_id()
        assert next_id in text
        loaded = yaml.safe_load(review.yaml_excerpt(review.get_entry(entry_id), next_id))
        assert loaded == [
            {
                "id": next_id,
                "question": "Combien coûte le BTS SIO ?",
                "expect": [
                    {"source": "bts-sio.html", "section": "Tarifs"},
                    {"source": "evil.html"},
                ],
                "answer_must": [],
            }
        ]

    def test_next_id_follows_the_eval_set_and_the_promoted_entries(self, tmp_path):
        questions = tmp_path / "questions.yaml"
        questions.write_text("- id: q07\n  question: a\n- id: q34\n  question: b\n")
        assert review.next_question_id(questions) == "q35"
        entry_id = add()
        review.mark_promoted(entry_id, "q40")
        assert review.next_question_id(questions) == "q41"
        assert review.next_question_id(tmp_path / "missing.yaml") == "q41"

    def test_the_real_eval_set_is_found(self):
        assert int(review.next_question_id()[1:]) > 34

    def test_a_refusal_is_exported_as_out_of_scope(self, signed_in):
        entry_id = add(
            "Quel temps à Lyon ?", result={"grade": "refuse", "retrieved": [], "sources": []}
        )
        loaded = yaml.safe_load(review.yaml_excerpt(review.get_entry(entry_id), "q99"))
        assert loaded == [
            {"id": "q99", "question": "Quel temps à Lyon ?", "out_of_scope": "threshold"}
        ]

    def test_a_follow_up_is_exported_through_its_rewrite(self):
        entry_id = add("Et à Lyon ?", rewritten="Le BTS SIO est-il proposé à Lyon ?")
        loaded = yaml.safe_load(review.yaml_excerpt(review.get_entry(entry_id), "q99"))
        assert loaded[0]["question"] == "Le BTS SIO est-il proposé à Lyon ?"

    def test_quotes_and_colons_survive_the_yaml(self):
        entry_id = add('Quel est le "prix": 100 € ?')
        loaded = yaml.safe_load(review.yaml_excerpt(review.get_entry(entry_id), "q99"))
        assert loaded[0]["question"] == 'Quel est le "prix": 100 € ?'

    def test_marking_an_entry_as_promoted(self, signed_in):
        entry_id = add()
        resp = signed_in.post(f"/admin/reponses/{entry_id}/promotion", data={"question_id": "q77"})
        assert resp.status_code == 303
        assert review.get_entry(entry_id)["promoted_as"] == "q77"
        assert "q77" in signed_in.get(f"/admin/reponses/{entry_id}").text
        # the excerpt keeps the id that was used
        assert "q77" in signed_in.get(f"/admin/reponses/{entry_id}/yaml").text

    @pytest.mark.parametrize("question_id", ["", "x1", "q", "q12345", "q1; DROP"])
    def test_invalid_question_ids_are_refused(self, signed_in, question_id):
        entry_id = add()
        resp = signed_in.post(
            f"/admin/reponses/{entry_id}/promotion", data={"question_id": question_id}
        )
        assert resp.status_code == 404
        assert review.get_entry(entry_id)["promoted_as"] is None

    def test_unknown_entry(self, signed_in):
        assert signed_in.get("/admin/reponses/999/yaml").status_code == 404
        resp = signed_in.post("/admin/reponses/999/promotion", data={"question_id": "q50"})
        assert resp.status_code == 404


class TestSummary:
    @staticmethod
    def _age(entry_id: int, days: int) -> None:
        old = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with db() as conn:
            conn.execute("UPDATE answer_log SET created_at = ? WHERE id = ?", (old, entry_id))

    @staticmethod
    def _fill() -> dict[str, int]:
        ids = {
            "good": add(),
            "wrong": add(
                "Quel est le prix ?",
                result={"retrieved": [{"source": "a.html", "section": "S", "score": 0.52}]},
            ),
            "off": add(
                "Quel temps à Lyon ?",
                result={
                    "grade": "refuse",
                    "answer": "Je n'ai pas trouvé...",
                    "sources": [],
                    "retrieved": [{"source": "b.html", "section": "T", "score": 0.41}],
                    "llm_model": None,
                },
            ),
            "hello": add(
                "Bonjour",
                result={"retrieved": [], "sources": [], "llm_model": None},
            ),
        }
        store.record(channel="api", question="Q ?", error="LLMUnavailableError: 429 budget")
        review.review(ids["good"], "bonne")
        review.review(ids["wrong"], "fausse")
        review.review(ids["off"], "hors_sujet")
        return ids

    def test_needs_the_login(self, client):
        resp = client.get("/admin/synthese")
        assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"

    def test_an_empty_journal_says_so(self, signed_in):
        resp = signed_in.get("/admin/synthese")
        assert resp.status_code == 200 and "Aucune réponse sur cette période" in resp.text

    def test_counts_how_the_answers_end_and_how_they_were_reviewed(self, signed_in):
        self._fill()
        data = stats.summary()
        assert data["totals"]["total"] == 5 and data["totals"]["reviewed"] == 3
        assert {r: v["n"] for r, v in data["by_route"].items()} == {
            "generate": 2,
            "refuse": 1,
            "smalltalk": 1,
            "error": 1,
        }
        assert data["crosstab"][("generate", "bonne")] == 1
        assert data["crosstab"][("generate", "fausse")] == 1
        assert data["crosstab"][("refuse", "hors_sujet")] == 1
        assert data["crosstab"][("smalltalk", "")] == 1  # not reviewed yet
        page = signed_in.get("/admin/synthese").text
        assert "Comment les réponses se terminent" in page and "3 revue(s)" in page

    def test_scores_per_review_sit_next_to_the_threshold(self, signed_in):
        self._fill()
        data = stats.summary()
        assert data["by_label"]["bonne"]["max_score"] == 0.71
        assert data["by_label"]["fausse"]["min_score"] == 0.52
        assert data["by_label"]["hors_sujet"]["avg_score"] == 0.41
        page = signed_in.get("/admin/synthese").text
        assert "Seuil actuel : 0,47" in page and "0,52" in page and "0,41" in page

    def test_shows_the_models_and_the_errors(self, signed_in):
        self._fill()
        data = stats.summary()
        models = {m["model"]: m["n"] for m in data["by_model"]}
        assert models == {"mistral-medium-2508": 2, "": 1}  # "" : the error, before any answer
        page = signed_in.get("/admin/synthese").text
        assert "mistral-medium-2508" in page and "LLMUnavailableError: 429 budget" in page

    def test_a_period_leaves_out_the_older_entries(self, signed_in):
        ids = self._fill()
        self._age(ids["good"], 40)
        self._age(ids["wrong"], 10)
        assert stats.summary("")["totals"]["total"] == 5
        assert stats.summary("30")["totals"]["total"] == 4
        assert stats.summary("7")["totals"]["total"] == 3
        assert stats.summary("nimporte quoi")["totals"]["total"] == 5  # unknown: all of it
        assert "7 derniers jours" in signed_in.get("/admin/synthese?periode=7").text

    def test_what_comes_from_the_journal_is_escaped(self, signed_in):
        add(result={"llm_model": "<script>alert(1)</script>"})
        store.record(channel="api", question="Q ?", error="<img src=x onerror=alert(1)>")
        page = signed_in.get("/admin/synthese").text
        assert "<script>" not in page and "<img" not in page
        assert "&lt;script&gt;" in page and "&lt;img" in page

    def test_the_other_pages_link_to_it(self, signed_in):
        assert 'href="/admin/synthese"' in signed_in.get("/admin/").text


def rate(entry_id: int, value: int, comment: str | None = None, at: str | None = "now") -> None:
    """Give an entry the thumb that chat/feedback.py would copy (at=None: an earlier feedback
    taken over by the migration, whose date is unknown)."""
    when = datetime.now(UTC).isoformat() if at == "now" else at
    with db() as conn:
        conn.execute(
            "UPDATE answer_log SET feedback = ?, feedback_comment = ?, feedback_at = ? "
            "WHERE id = ?",
            (value, comment, when, entry_id),
        )


class TestFeedbackInTheList:
    @staticmethod
    def _fill() -> dict[str, int]:
        ids = {
            "useful": add("Question utile"),
            "not_useful": add("Question pas utile"),
            "none": add("Question sans avis"),
            "api": add("Question par API", channel="api"),
        }
        rate(ids["useful"], 1)
        rate(ids["not_useful"], 0, "Il manque le prix")
        return ids

    @staticmethod
    def _shown(client, **params) -> str:
        return client.get("/admin/", params=params).text

    def test_the_filters_match_the_choices_of_the_form(self):
        assert set(pages.FEEDBACK_CHOICES) == set(review.FEEDBACK_FILTERS)

    def test_each_feedback_filter(self, signed_in):
        self._fill()
        useful = self._shown(signed_in, avis="positif")
        assert "Question utile" in useful and "Question pas utile" not in useful
        assert "Question sans avis" not in useful
        not_useful = self._shown(signed_in, avis="negatif")
        assert "Question pas utile" in not_useful and "Question utile<" not in not_useful
        none = self._shown(signed_in, avis="sans")
        assert "Question sans avis" in none and "Question utile" not in none
        assert "Question par API" not in none  # the API is never rated: not "without feedback"
        anything = self._shown(signed_in, avis="nimporte")  # unknown: no filter
        assert "4 réponse(s)" in anything

    def test_the_feedback_filter_goes_with_the_review_filter(self, signed_in):
        self._fill()
        reviewed = add("Question pas utile et revue")
        rate(reviewed, 0)
        review.review(reviewed, "bonne")
        text = self._shown(signed_in, avis="negatif", statut="unreviewed")
        assert "Question pas utile<" in text and "Question pas utile et revue" not in text
        assert "1 réponse(s)" in text

    def test_the_column_shows_the_thumbs_with_words(self, signed_in):
        self._fill()
        text = self._shown(signed_in)
        assert "<th>Avis</th>" in text
        assert 'title="Utile"' in text and "👍" in text and '<span class="sr">Utile</span>' in text
        assert 'title="Pas utile"' in text and "👎" in text

    def test_the_shortcut_counts_the_unreviewed_negative_feedback(self, signed_in):
        ids = self._fill()
        other = add("Autre question pas utile")
        rate(other, 0)
        review.review(ids["not_useful"], "partielle")  # reviewed: no longer counted
        assert review.count_unreviewed_negative() == 1
        text = self._shown(signed_in)
        assert "Avis négatifs non revus (1)" in text
        assert 'href="/admin/?avis=negatif&amp;statut=unreviewed"' in text

    def test_the_form_keeps_the_chosen_feedback(self, signed_in):
        text = self._shown(signed_in, avis="negatif")
        assert '<option value="negatif" selected>Pas utile</option>' in text

    def test_the_pager_keeps_the_feedback_filter(self, signed_in):
        for number in range(review.PAGE_SIZE + 1):
            rate(add(f"Question {number}"), 0)
        text = self._shown(signed_in, avis="negatif")
        assert "avis=negatif&amp;page=2" in text


class TestFeedbackInTheDetail:
    def test_a_feedback_with_its_comment(self, signed_in):
        entry_id = add()
        comment = "Le prix est faux\n<script>alert(1)</script>"
        rate(entry_id, 0, comment, "2026-10-12T09:30:00+00:00")
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert "Avis de l'utilisateur" in text
        assert "Pas utile" in text and "12/10 09:30 (UTC)" in text
        assert "<script>alert(1)" not in text
        assert "Le prix est faux\n&lt;script&gt;alert(1)&lt;/script&gt;" in text

    def test_a_feedback_without_comment(self, signed_in):
        entry_id = add()
        rate(entry_id, 1)
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert "👍" in text and "Utile" in text and "Sans commentaire." in text

    def test_an_earlier_feedback_has_no_date(self, signed_in):
        entry_id = add()
        rate(entry_id, 1, at=None)
        text = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert "date inconnue (avis antérieur au 12 octobre 2026)" in text

    def test_no_feedback_yet(self, signed_in):
        text = signed_in.get(f"/admin/reponses/{add()}").text
        assert "Aucun avis." in text

    def test_the_api_has_no_feedback(self, signed_in):
        text = signed_in.get(f"/admin/reponses/{add(channel='api')}").text
        assert "Sans objet" in text and "Aucun avis." not in text


class TestFeedbackInTheSummary:
    @staticmethod
    def _fill() -> dict[str, int]:
        refused = {"grade": "refuse", "retrieved": [], "sources": [], "llm_model": None}
        hello = {"retrieved": [], "sources": [], "llm_model": None}
        ids = {
            "useful_false": add("Q1"),
            "useful": add("Q2"),
            "not_useful_good": add("Q3"),
            "silent": add("Q4"),
            "refused": add("Il fait beau ?", result=refused),
            "hello": add("Bonjour", result=hello),
            "api": add("Q par API", channel="api"),
        }
        rate(ids["useful_false"], 1)
        rate(ids["useful"], 1, "Merci, très clair")
        rate(ids["not_useful_good"], 0)
        rate(ids["refused"], 0)
        rate(ids["hello"], 1)
        review.review(ids["useful_false"], "fausse")
        review.review(ids["not_useful_good"], "bonne")
        return ids

    def test_counts_per_route_without_the_api(self):
        self._fill()
        feedback = stats.summary()["feedback"]
        assert feedback["by_route"] == {
            "generate": {"answers": 4, "rated": 3, "useful": 2, "not_useful": 1, "comments": 1},
            "refuse": {"answers": 1, "rated": 1, "useful": 0, "not_useful": 1, "comments": 0},
            "smalltalk": {"answers": 1, "rated": 1, "useful": 1, "not_useful": 0, "comments": 0},
        }
        # The greeting's thumb is left out of the total
        assert feedback["total_without_smalltalk"] == {
            "answers": 5,
            "rated": 4,
            "useful": 2,
            "not_useful": 2,
            "comments": 1,
        }
        assert feedback["comments"] == 1

    def test_crosses_the_thumbs_with_the_review(self):
        self._fill()
        crosstab = stats.summary()["feedback"]["crosstab"]
        assert crosstab == {(1, "fausse"): 1, (1, ""): 2, (0, "bonne"): 1, (0, ""): 1}

    def test_the_page_shows_the_rates_with_their_votes(self, signed_in):
        self._fill()
        page = signed_in.get("/admin/synthese").text
        assert "Avis des utilisateurs" in page and "Total hors politesse" in page
        assert "67 % (3 votes)" in page  # generated answers
        assert "0 % (1 vote)" in page  # the refusal
        assert "50 % (4 votes)" in page  # in all, without the greeting
        assert "1 avis avec un commentaire" in page

    def test_the_page_points_at_useful_but_false_answers(self, signed_in):
        self._fill()
        page = signed_in.get("/admin/synthese").text
        assert "1 réponse(s) jugée(s) « Utile »" in page
        assert 'href="/admin/?avis=positif&amp;statut=fausse"' in page

    def test_no_vote_shows_a_dash_not_a_rate(self, signed_in):
        add()
        page = signed_in.get("/admin/synthese").text
        assert "—" in page and "Avis des utilisateurs et revue" not in page
        assert stats.summary()["feedback"]["crosstab"] == {}

    def test_a_period_with_only_api_answers(self, signed_in):
        add(channel="api")
        page = signed_in.get("/admin/synthese").text
        assert "Aucune réponse du chat sur cette période." in page

    def test_an_empty_journal_gives_zeros(self):
        feedback = stats.summary("7")["feedback"]
        assert feedback["by_route"] == {} and feedback["crosstab"] == {}
        assert set(feedback["total_without_smalltalk"].values()) == {0}
        assert pages._satisfaction(0, 0) == "—"

    def test_the_period_applies_to_the_thumbs(self):
        ids = self._fill()
        old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        with db() as conn:
            conn.execute(
                "UPDATE answer_log SET created_at = ? WHERE id IN (?, ?)",
                (old, ids["useful_false"], ids["useful"]),
            )
        feedback = stats.summary("7")["feedback"]
        assert feedback["by_route"]["generate"]["useful"] == 0
        assert feedback["crosstab"].get((1, "fausse"), 0) == 0


DOES_NOT_KNOW = "Le contexte ne précise pas quels BTS sont accessibles via Parcoursup."


class TestUnansweredQuestions:
    """The questions left without an answer (#20) in the list, the detail and the summary."""

    @staticmethod
    def _fill() -> dict[str, int]:
        refused = {"grade": "refuse", "retrieved": [], "sources": [], "llm_model": None}
        ids = {
            "answered": add("Question avec réponse"),
            "refused": add("Question refusée", result=refused),
            "unknown": add("Question sans info", result={"answer": DOES_NOT_KNOW}),
            "partial": add(
                "Question en partie",
                result={"answer": "Environ 7 000 €. Le contexte ne précise pas la rentrée."},
            ),
            "not_useful": add("Question pas utile"),
        }
        rate(ids["not_useful"], 0)
        return ids

    def test_the_choices_of_the_form_are_the_filters(self):
        assert set(pages.GAP_CHOICES) == set(review.GAP_GROUPS) | set(gaps.GAP_KINDS)

    def test_the_filter_of_the_list(self, signed_in):
        self._fill()

        def shown(**params) -> str:
            return signed_in.get("/admin/", params=params).text

        any_kind = shown(manque="tous")
        assert "4 réponse(s)" in any_kind and "Question avec réponse" not in any_kind
        none = shown(manque="aucune")
        assert "Question refusée" in none and "Question sans info" in none
        assert "Question en partie" not in none and "Question pas utile" not in none
        assert "1 réponse(s)" in shown(manque="incomplete")
        assert "5 réponse(s)" in shown(manque='"><script>x</script>')  # unknown: no filter
        assert "<script>x" not in shown(manque='"><script>x</script>')

    def test_the_form_and_the_pager_keep_the_filter(self, signed_in):
        for number in range(review.PAGE_SIZE + 1):
            add(f"Question {number}", result={"answer": DOES_NOT_KNOW})
        text = signed_in.get("/admin/", params={"manque": "aveu"}).text
        assert '<option value="aveu" selected>Le modèle ne sait pas</option>' in text
        assert "manque=aveu&amp;page=2" in text

    def test_the_list_tags_the_kind_but_not_twice_a_refusal(self, signed_in):
        self._fill()
        text = signed_in.get("/admin/").text
        assert '<span class="tag">Le modèle ne sait pas</span>' in text
        assert '<span class="tag">Réponse incomplète</span>' in text
        assert '<span class="tag">Jugée « Pas utile »</span>' in text
        assert text.count("Refus au seuil</span>") == 1  # the route only

    def test_the_detail_says_whether_the_question_went_without_an_answer(self, signed_in):
        ids = self._fill()

        def line(entry_id: int) -> str:
            text = signed_in.get(f"/admin/reponses/{entry_id}").text
            return text.split("<dt>Sans réponse</dt><dd>")[1].split("</dd>")[0]

        assert line(ids["unknown"]) == "Le modèle ne sait pas"
        assert line(ids["refused"]) == "Refus au seuil"
        assert line(ids["answered"]) == "Non"
        hello = add("Bonjour", result={"retrieved": [], "sources": [], "llm_model": None})
        assert line(hello) == "–"

    def test_the_summary_counts_them_with_links(self, signed_in):
        self._fill()
        add("Bonjour", result={"retrieved": [], "sources": [], "llm_model": None})
        page = signed_in.get("/admin/synthese").text
        assert "Questions sans réponse" in page and "Sur les 5 question(s)" in page
        assert "<strong>Sans aucune réponse</strong>" in page
        assert 'href="/admin/?manque=aucune"' in page and 'href="/admin/?manque=refus"' in page
        assert 'href="/admin/?manque=hors_ynov"' not in page  # nothing to show: no link
        assert "40 %" in page  # 2 of the 5 questions got no answer at all

    def test_a_summary_with_greetings_only(self, signed_in):
        add("Bonjour", result={"retrieved": [], "sources": [], "llm_model": None})
        page = signed_in.get("/admin/synthese").text
        assert "Aucune question sur cette période (hors politesse)." in page


REFUSED = {"grade": "refuse", "retrieved": [], "sources": [], "llm_model": None}


def unanswered(question: str = "Y a-t-il des logements étudiants ?", theme: str = "") -> int:
    """An entry refused at the threshold, put in `theme` when given."""
    entry_id = add(question, result=REFUSED)
    if theme:
        assert themes.move(entry_id, new_name=theme) is None
    return entry_id


def theme_id(name: str) -> int:
    return next(t["id"] for t in themes.choices() if t["name"] == name)


class TestThemePages:
    """/admin/sans-reponse (#20): the themes, the grouping button, a theme and its decisions."""

    @pytest.fixture(autouse=True)
    def no_search(self, monkeypatch):
        """The theme page asks the search what it finds today: Qdrant is not there in tests."""
        self.searched: list[str] = []

        def search(question: str) -> list[dict]:
            self.searched.append(question)
            return [
                {"source": "vie.html", "section": "Logement", "title": "Vie étudiante",
                 "url": "https://www.ynov.com/vie", "score": 0.52},
                {"source": "x.html", "section": "Autre", "title": None, "url": "javascript:x",
                 "score": 0.31},
            ]  # fmt: skip

        monkeypatch.setattr(themes, "current_search", search)

    def test_the_pages_need_a_session(self, client):
        theme = theme_id_after(unanswered(theme="Logement étudiant"))
        for path in ("/admin/sans-reponse", f"/admin/sans-reponse/{theme}"):
            resp = client.get(path)
            assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"
        for path in (
            "/admin/sans-reponse/regrouper",
            f"/admin/sans-reponse/{theme}/nom",
            f"/admin/sans-reponse/{theme}/cause",
            f"/admin/sans-reponse/{theme}/fusion",
            "/admin/reponses/1/theme",
        ):
            resp = client.post(path, data={"nom": "X", "cause": "contenu", "cible": "1"})
            assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"
        assert themes.get_theme(theme)["name"] == "Logement étudiant"

    def test_the_list_of_themes(self, signed_in):
        unanswered("Un logement à Lyon ?", "Logement étudiant")
        unanswered("Une chambre ?", "Logement étudiant")
        unanswered("<script>alert(1)</script>", "Date de rentrée")
        unanswered("Pas encore rangée ?")
        add("Question avec réponse")
        resp = signed_in.get("/admin/sans-reponse")
        page = resp.text
        assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in resp.headers["content-security-policy"]
        assert page.index("Logement étudiant") < page.index("Date de rentrée")  # most asked first
        assert "À qualifier" in page and "Une chambre ?" in page  # the example
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "<script>" not in page
        assert "Questions non regroupées : 1" in page and "Pas encore rangée ?" in page
        assert "Regrouper 1 nouvelle(s) question(s) (1 appel au LLM)" in page
        assert "Question avec réponse" not in page
        assert '<a href="/admin/sans-reponse">Sans réponse</a>' in page  # the navigation

    def test_no_button_when_everything_is_grouped(self, signed_in):
        unanswered(theme="Logement étudiant")
        page = signed_in.get("/admin/sans-reponse").text
        assert "Regrouper" not in page and "Toutes les questions sans réponse sont rangées" in page

    def test_the_period(self, signed_in):
        old = unanswered("Ancienne question", "Vieux thème")
        unanswered("Récente", "Logement étudiant")
        with db() as conn:
            conn.execute(
                "UPDATE answer_log SET created_at = '2026-01-01T00:00:00+00:00' WHERE id = ?",
                (old,),
            )
        page = signed_in.get("/admin/sans-reponse", params={"periode": "7"}).text
        assert "Vieux thème" not in page and "Logement étudiant" in page
        assert '<option value="7" selected>' in page
        assert "Vieux thème" in signed_in.get("/admin/sans-reponse?periode=x").text

    def test_grouping_from_the_button(self, signed_in, monkeypatch):
        unanswered("Un logement ?")
        unanswered("HEC ?")
        calls: list[dict] = []

        def llm(payload: dict, timeout: float = 30.0) -> dict:
            calls.append(payload)
            content = '{"1": "Logement étudiant", "2": "Autres écoles"}'
            return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}

        monkeypatch.setattr(themes, "chat_completion", llm)
        resp = signed_in.post("/admin/sans-reponse/regrouper")
        assert resp.status_code == 303 and len(calls) == 1
        assert resp.headers["location"] == (
            "/admin/sans-reponse?resultat=ok&questions=2&nouveaux=2"
        )
        page = signed_in.get(resp.headers["location"]).text
        assert "2 question(s) rangée(s), dont 2 dans de nouveaux thèmes." in page
        assert "Logement étudiant" in page and "Question hors sujet" in page  # fixed theme

    def test_a_failed_grouping_says_so(self, signed_in, monkeypatch):
        from graph.llm import LLMUnavailableError

        unanswered("Un logement ?")

        def down(payload: dict, timeout: float = 30.0) -> dict:
            raise LLMUnavailableError("429 budget")

        monkeypatch.setattr(themes, "chat_completion", down)
        resp = signed_in.post("/admin/sans-reponse/regrouper")
        page = signed_in.get(resp.headers["location"]).text
        assert "Le LLM n&#x27;a pas répondu : rien n&#x27;a été rangé" in page
        assert themes.choices() == []

    def test_messages_come_from_fixed_texts_only(self, signed_in):
        page = signed_in.get(
            "/admin/sans-reponse",
            params={"resultat": "<script>x</script>", "questions": "-3", "nouveaux": "1"},
        ).text
        assert "<script>x" not in page and "question(s) rangée(s)" not in page
        page = signed_in.get(
            "/admin/sans-reponse", params={"resultat": "ok", "questions": "-3"}
        ).text
        assert "Aucune question à ranger." in page
        assert signed_in.get("/admin/sans-reponse?questions=abc").status_code == 422

    def test_a_foreign_origin_cannot_start_a_grouping(self, signed_in, monkeypatch):
        unanswered("Un logement ?")
        monkeypatch.setattr(themes, "chat_completion", lambda *_a, **_k: pytest.fail("LLM"))
        resp = signed_in.post(
            "/admin/sans-reponse/regrouper", headers={"Origin": "https://evil.example"}
        )
        assert resp.status_code == 403

    def test_a_theme(self, signed_in):
        entry_id = unanswered("Un logement à Lyon ?", "Logement étudiant")
        theme = theme_id_after(entry_id)
        page = signed_in.get(f"/admin/sans-reponse/{theme}").text
        assert "Thème : Logement étudiant" in page
        assert self.searched == ["Un logement à Lyon ?"]
        assert "Ce que la recherche trouve aujourd" in page and "≥ seuil" in page
        assert '<a href="https://www.ynov.com/vie" rel="noopener noreferrer">' in page
        assert "javascript:x" not in page
        assert f'href="/admin/reponses/{entry_id}"' in page
        assert f'action="/admin/reponses/{entry_id}/theme"' in page
        assert f'name="retour" value="{theme}"' in page
        assert "Suggestion" not in page and "Fusionner" not in page  # no other theme

    def test_a_theme_when_the_search_fails(self, signed_in, monkeypatch):
        def broken(question: str) -> list[dict]:
            raise ConnectionError("qdrant")

        monkeypatch.setattr(themes, "current_search", broken)
        theme = theme_id_after(unanswered(theme="Logement étudiant"))
        resp = signed_in.get(f"/admin/sans-reponse/{theme}")
        assert resp.status_code == 200 and "La recherche ne répond pas" in resp.text

    def test_an_unknown_theme(self, signed_in):
        assert signed_in.get("/admin/sans-reponse/999").status_code == 404
        assert signed_in.post("/admin/sans-reponse/999/cause").status_code == 404

    def test_the_suggestion_of_a_fixed_theme(self, signed_in):
        theme = theme_id_after(unanswered("HEC ?", "Autres écoles"))
        themes.set_cause(theme, None)
        page = signed_in.get(f"/admin/sans-reponse/{theme}").text
        assert "Suggestion : Question hors sujet" in page

    def test_choosing_the_cause(self, signed_in):
        entry_id = unanswered(theme="Logement étudiant")
        theme = theme_id_after(entry_id)
        resp = signed_in.post(
            f"/admin/sans-reponse/{theme}/cause",
            data={"cause": "recherche", "note": "La page existe : <b>vie étudiante</b>"},
        )
        assert resp.status_code == 303
        found = themes.get_theme(theme)
        assert found["cause"] == "recherche"
        page = signed_in.get(f"/admin/sans-reponse/{theme}").text
        assert "&lt;b&gt;vie étudiante&lt;/b&gt;" in page
        assert f'href="/admin/reponses/{entry_id}/yaml"' in page  # back to eval/
        listing = signed_in.get("/admin/sans-reponse").text
        assert "Défaut de recherche du chatbot" in listing
        resp = signed_in.post(f"/admin/sans-reponse/{theme}/cause", data={"cause": "autre"})
        assert resp.status_code == 400 and themes.get_theme(theme)["cause"] == "recherche"
        signed_in.post(f"/admin/sans-reponse/{theme}/cause", data={"cause": ""})
        assert themes.get_theme(theme)["cause"] is None

    def test_renaming(self, signed_in):
        theme = theme_id_after(unanswered(theme="Logement"))
        unanswered("Rentrée ?", "Date de <b>rentrée</b>")
        resp = signed_in.post(f"/admin/sans-reponse/{theme}/nom", data={"nom": "Logement étudiant"})
        assert resp.status_code == 303 and themes.get_theme(theme)["name"] == "Logement étudiant"
        resp = signed_in.post(f"/admin/sans-reponse/{theme}/nom", data={"nom": "date de rentrée"})
        assert resp.status_code == 400 and "fusionnez plutôt" in resp.text
        assert "Date de rentrée" in resp.text  # the tag was cleaned from the name

    def test_merging(self, signed_in):
        source = theme_id_after(unanswered("Un logement ?", "Logement"))
        target = theme_id_after(unanswered("Une chambre ?", "Logement étudiant"))
        page = signed_in.get(f"/admin/sans-reponse/{source}").text
        assert f'<option value="{target}">Logement étudiant</option>' in page
        resp = signed_in.post(f"/admin/sans-reponse/{source}/fusion", data={"cible": str(target)})
        assert resp.status_code == 303 and resp.headers["location"] == (
            f"/admin/sans-reponse/{target}"
        )
        assert themes.get_theme(source) is None and themes.get_theme(target)["questions"] == 2
        for bad in ("", "abc", str(target), "999"):
            resp = signed_in.post(f"/admin/sans-reponse/{target}/fusion", data={"cible": bad})
            assert resp.status_code == 400

    def test_moving_a_question_from_its_theme_page(self, signed_in):
        entry_id = unanswered("Un logement ?", "Logement")
        source = theme_id_after(entry_id)
        target = theme_id_after(unanswered("Une chambre ?", "Logement étudiant"))
        resp = signed_in.post(
            f"/admin/reponses/{entry_id}/theme",
            data={"theme": str(target), "retour": str(source)},
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/admin/sans-reponse/{source}"
        assert theme_id_after(entry_id) == target
        resp = signed_in.post(
            f"/admin/reponses/{entry_id}/theme",
            data={"theme": "", "nouveau": "Résidences", "retour": "https://evil.example"},
        )
        assert resp.headers["location"] == f"/admin/reponses/{entry_id}"  # never elsewhere
        assert themes.get_theme(theme_id_after(entry_id))["name"] == "Résidences"
        signed_in.post(f"/admin/reponses/{entry_id}/theme", data={"theme": ""})
        assert themes.pending_counts()["questions"] == 1  # back to the next grouping

    def test_moving_refuses_what_is_not_there(self, signed_in):
        entry_id = unanswered(theme="Logement")
        for data in ({"theme": "999"}, {"theme": "abc"}, {"theme": "", "nouveau": "<>"}):
            resp = signed_in.post(f"/admin/reponses/{entry_id}/theme", data=data)
            assert resp.status_code == 400
        answered = add("Question avec réponse")
        resp = signed_in.post(f"/admin/reponses/{answered}/theme", data={"nouveau": "X"})
        assert resp.status_code == 400 and "pas une question sans réponse" in resp.text
        assert signed_in.post("/admin/reponses/999/theme").status_code == 404

    def test_the_detail_of_an_answer_shows_its_theme(self, signed_in):
        entry_id = unanswered(theme="Logement & résidences")
        theme = theme_id_after(entry_id)
        page = signed_in.get(f"/admin/reponses/{entry_id}").text
        assert f'<a href="/admin/sans-reponse/{theme}">Logement &amp; résidences</a>' in page
        assert f'action="/admin/reponses/{entry_id}/theme"' in page
        pending = unanswered("Pas encore rangée ?")
        assert "Pas encore rangée dans un thème" in signed_in.get(f"/admin/reponses/{pending}").text
        answered = add("Question avec réponse")
        assert "<h2>Thème</h2>" not in signed_in.get(f"/admin/reponses/{answered}").text

    def test_the_summary_links_to_the_themes(self, signed_in):
        unanswered()
        assert 'href="/admin/sans-reponse"' in signed_in.get("/admin/synthese").text


def theme_id_after(entry_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT gap_theme_id FROM answer_log WHERE id = ?", (entry_id,))
        return int(row.fetchone()[0])


class TestReportPage:
    """/admin/rapport (#20): the monthly report, in /admin and as a file of its own."""

    @staticmethod
    def _this_month() -> str:
        return report.month_label(report.current_month())

    def test_needs_the_login(self, client):
        for path in ("/admin/rapport", "/admin/rapport?mois=2026-10&telecharger=1"):
            resp = client.get(path)
            assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"

    def test_the_current_month_by_default(self, signed_in):
        unanswered("Un logement à Lyon ?", "Logement étudiant")
        unanswered("Une chambre ?", "Logement étudiant")
        resp = signed_in.get("/admin/rapport")
        page = resp.text
        assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in resp.headers["content-security-policy"]
        assert f"Questions sans réponse : {self._this_month()}" in page
        assert '<a href="/admin/rapport">Rapport</a>' in page  # the navigation
        month = report.current_month()
        assert f'<option value="{month}" selected>' in page
        assert f'href="/admin/rapport?mois={month}&amp;telecharger=1"' in page
        assert "Logement étudiant" in page and "À vérifier" in page
        assert "@media print" in page

    @pytest.mark.parametrize("month", ["2026-13", "../../etc", "x" * 50, "2026-10'"])
    def test_an_invalid_month_shows_the_current_one(self, signed_in, month):
        resp = signed_in.get("/admin/rapport", params={"mois": month})
        assert resp.status_code == 200 and self._this_month() in resp.text

    def test_the_month_selector_lists_the_months_of_the_journal(self, signed_in):
        entry_id = unanswered()
        with db() as conn:
            conn.execute(
                "UPDATE answer_log SET created_at = '2026-03-10T10:00:00+00:00' WHERE id = ?",
                (entry_id,),
            )
        page = signed_in.get("/admin/rapport?mois=2026-03").text
        assert '<option value="2026-03" selected>mars 2026</option>' in page
        assert f'<option value="{report.current_month()}">' in page
        assert "1 question posée au chatbot en mars 2026" in page

    def test_an_empty_month(self, signed_in):
        page = signed_in.get("/admin/rapport?mois=2020-01").text
        assert "Aucune question n'a été posée au chatbot en janvier 2020" in page
        assert "Comment lire ce rapport" in page

    def test_the_download(self, signed_in):
        unanswered("Un logement à Lyon ?", "Logement étudiant")
        unanswered("Pas encore rangée ?")
        month = report.current_month()
        resp = signed_in.get("/admin/rapport", params={"mois": month, "telecharger": "1"})
        assert resp.status_code == 200
        assert resp.headers["content-disposition"] == (
            f'attachment; filename="rapport-questions-sans-reponse-{month}.html"'
        )
        assert resp.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in resp.headers["content-security-policy"]
        html = resp.text
        assert html.startswith("<!doctype html>") and "<style>" in html and "@media print" in html
        assert "/admin" not in html and "<a " not in html and "<form" not in html
        assert 'http-equiv="Content-Security-Policy"' in html  # still locked from the disk
        assert "Logement étudiant" in html
        assert "1 question du mois sans thème" in html  # said without a link

    def test_the_file_name_comes_from_the_validated_month(self, signed_in):
        resp = signed_in.get(
            "/admin/rapport", params={"mois": '2026-10"; x="y', "telecharger": "1"}
        )
        month = report.current_month()
        assert resp.headers["content-disposition"] == (
            f'attachment; filename="rapport-questions-sans-reponse-{month}.html"'
        )

    def test_unthemed_questions_are_pointed_to_in_the_page(self, signed_in):
        unanswered("Pas encore rangée ?")
        page = signed_in.get("/admin/rapport").text
        assert "1 question du mois pas encore rangée par thème" in page
        assert '<a href="/admin/sans-reponse">regroupez-la' in page

    def test_content_is_escaped(self, signed_in):
        for thread in ("a", "b"):  # two conversations: the examples are quoted
            entry_id = add("<script>alert(1)</script>", result=REFUSED, thread_id=thread)
            assert themes.move(entry_id, new_name="Logement <b>étudiant</b> & co") is None
        theme = theme_id_after(entry_id)
        themes.set_cause(theme, "contenu", "<img src=x onerror=alert(1)>")
        for path in ("/admin/rapport", "/admin/rapport?telecharger=1"):
            html = signed_in.get(path).text
            assert "<script>" not in html and "<img" not in html and "<b>" not in html
            assert "« &lt;script&gt;alert(1)&lt;/script&gt; »" in html
            assert "Logement étudiant &amp; co" in html
            assert "&lt;img src=x onerror=alert(1)&gt;" in html

    def test_a_single_conversation_is_not_quoted(self, signed_in):
        unanswered("Ma question très personnelle ?", "Logement étudiant")
        page = signed_in.get("/admin/rapport").text
        assert "Ma question très personnelle" not in page
        assert "1 conversation : question non citée" in page

    def test_sections_by_cause(self, signed_in):
        unanswered("Un logement ?", "Logement étudiant")
        unanswered("Le prix du BTS SIO ?", "Frais de scolarité")
        unanswered("Quel temps fait-il ?", "Hors sujet")
        themes.set_cause(theme_id("Logement étudiant"), "contenu")
        themes.set_cause(theme_id("Frais de scolarité"), "recherche", "Repris en q35.")
        page = signed_in.get("/admin/rapport").text
        site = page.index("Ce que les visiteurs cherchent et que le site ne dit pas")
        chatbot = page.index("Questions auxquelles le chatbot aurait dû répondre")
        off = page.index("Questions hors sujet")
        assert site < page.index("Logement étudiant") < chatbot
        assert chatbot < page.index("Frais de scolarité") < off
        assert "Repris en q35." in page and "<th>Suivi</th>" in page
        assert "Hors sujet : 1 question" in page
        for jargon in ("seuil", "score", "chunk", "LLM"):
            body = page[page.index("<h2>En bref</h2>") :]
            assert jargon not in body, jargon


class TestDashboardPage:
    """/admin/tableau-de-bord (#16): the measured quality, from fictitious run files."""

    @staticmethod
    def write_run(folder: Path, run_id: str, environment: str = "local", **extra) -> None:
        lines = extra.pop(
            "results",
            [{"question_id": "q01", "question": "Combien ?", "verdict": "correct", "passed": True}],
        )
        run = {
            "schema_version": eval_results.SCHEMA_VERSION,
            "run_id": run_id,
            "date": run_id[:10],
            "kind": "e2e",
            "environment": environment,
            "question_set": "v13",
            "milestone": True,
            "label": run_id[14:],
            "config": {},
            "summary": {},
            "results": lines,
            **extra,
        }
        (folder / f"{run_id}.json").write_text(json.dumps(run), encoding="utf-8")

    @pytest.fixture
    def runs_dir(self, tmp_path, monkeypatch) -> Path:
        folder = tmp_path / "results"
        folder.mkdir()
        monkeypatch.setattr(eval_results, "RESULTS_DIR", folder)
        return folder

    def test_redirects_to_the_login_without_a_cookie(self, client, runs_dir):
        resp = client.get("/admin/tableau-de-bord")
        assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"

    def test_sections_without_script(self, signed_in, runs_dir):
        self.write_run(runs_dir, "2026-10-02_01_local", config={"llm_model": "model-a"})
        self.write_run(runs_dir, "2026-10-03_01_preprod", "preprod")
        resp = signed_in.get("/admin/tableau-de-bord")
        assert resp.status_code == 200
        assert "script-src" not in resp.headers["content-security-policy"]
        page = resp.text
        assert "<script" not in page
        for title in (
            "En bref",
            "Qualité de bout en bout dans le temps",
            "Matrice question × passage",
            "Cas limites",
            "Fiabilité de la vérification automatique",
        ):
            assert f"<h2>{title}</h2>" in page, title
        assert 'role="img"' in page
        assert "model-a" in page
        assert '<a href="/admin/tableau-de-bord">Tableau de bord</a>' in page  # navigation

    def test_texts_of_the_run_files_are_escaped(self, signed_in, runs_dir):
        self.write_run(
            runs_dir,
            "2026-10-02_01_evil",
            label="<script>alert(1)</script>",
            config={"llm_model": "<b>model</b>"},
            results=[
                {
                    "question_id": "q01",
                    "question": "Combien ?",
                    "verdict": "partial",
                    "passed": False,
                    "review_note": "<img src=x onerror=alert(1)>",
                }
            ],
        )
        page = signed_in.get("/admin/tableau-de-bord?passages=tous").text
        assert "<script>alert" not in page and "<img src=x" not in page and "<b>model" not in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
        assert "partielle — &lt;img src=x onerror=alert(1)&gt;" in page
        assert "&lt;b&gt;model&lt;/b&gt;" in page

    def test_invalid_filters_fall_back_to_their_default(self, signed_in, runs_dir):
        self.write_run(runs_dir, "2026-10-02_01_local")
        resp = signed_in.get("/admin/tableau-de-bord?environnement=<x>&matrice=nope&passages=0")
        assert resp.status_code == 200
        page = resp.text
        assert '<option value="" selected>Tous</option>' in page
        assert '<option value="e2e" selected>Bout en bout</option>' in page
        assert '<option value="etapes" selected>Étapes clés</option>' in page

    def test_the_environment_filters_the_matrix(self, signed_in, runs_dir):
        self.write_run(runs_dir, "2026-10-02_01_local")
        self.write_run(runs_dir, "2026-10-03_01_preprod", "preprod")
        page = signed_in.get("/admin/tableau-de-bord?environnement=preprod").text
        matrix = page[page.index("<h2>Matrice question × passage</h2>") :]
        matrix = matrix[: matrix.index("<h2>Cas limites</h2>")]
        assert "<code>10-03_01</code> (préprod)" in matrix
        assert "10-02_01" not in matrix
        assert '<option value="preprod" selected>Préprod</option>' in page

    def test_unreadable_files_are_listed(self, signed_in, runs_dir):
        self.write_run(runs_dir, "2026-10-02_01_local")
        (runs_dir / "2026-10-02_02_broken.json").write_text("{", encoding="utf-8")
        page = signed_in.get("/admin/tableau-de-bord").text
        assert "<h2>Fichiers écartés</h2>" in page
        assert "2026-10-02_02_broken.json : JSON illisible" in page

    def test_no_run_at_all(self, signed_in, runs_dir):
        resp = signed_in.get("/admin/tableau-de-bord")
        assert resp.status_code == 200
        assert "Aucun passage d'évaluation lisible." in resp.text

    def test_the_summary_links_to_the_dashboard(self, signed_in):
        page = signed_in.get("/admin/synthese").text
        assert 'href="/admin/tableau-de-bord"' in page

    def test_room_for_the_indicators_of_the_journal(self, runs_dir):
        """The usage of the journal (#16, PR 3) comes in as HTML: a card and a section."""
        self.write_run(runs_dir, "2026-10-02_01_local")
        page = admin_dashboard.dashboard_page(
            eval_dashboard.load(),
            admin_dashboard.parse_filters(),
            usage_brief='<div class="card">USAGE-CARD</div>',
            usage="<h2>Usage réel</h2>",
        )
        brief = page[page.index("<h2>En bref</h2>") : page.index('<h2 class="sr">Filtres</h2>')]
        assert "USAGE-CARD" in brief
        assert page.index("Fiabilité de la vérification automatique") < page.index("Usage réel")
