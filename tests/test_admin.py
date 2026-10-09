"""Tests for the admin pages that review the answer journal (no LLM)."""

import secrets
import time
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from admin import auth
from admin.routes import mount_admin
from app import main
from app.core.config import settings
from app.core.security import add_security_middleware, limiter
from chat.db import db, init_db
from journal import review, store

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
