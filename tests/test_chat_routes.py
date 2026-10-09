"""Tests for the account pages and the conditional mount of the chat (no LLM)."""

import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.core.config import settings
from app.core.security import limiter
from chat import accounts, pages
from chat.db import init_db
from chat.messages import AUTHOR
from chat.mount import mount_chat

CODE = re.compile(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){3}")


@pytest.fixture(autouse=True)
def chat_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "chat.db"))
    accounts._failures.clear()
    limiter.reset()  # the account pages are limited per IP: every test starts from zero
    init_db()


def signup(client, pseudo="alice", password="mot-de-passe-1", confirm=None):
    return client.post(
        "/compte/inscription",
        data={
            "pseudo": pseudo,
            "password": password,
            "confirm": password if confirm is None else confirm,
        },
    )


class TestPages:
    @pytest.mark.parametrize("path", ["inscription", "recuperation", "suppression"])
    def test_forms_are_served(self, client, path):
        resp = client.get(f"/compte/{path}")
        assert resp.status_code == 200
        assert "<form" in resp.text and 'lang="fr"' in resp.text

    def test_signup_tells_what_is_kept_of_the_questions(self, client):
        assert "conservées 6 mois" in client.get("/compte/inscription").text

    def test_signup_shows_the_recovery_code_once(self, client):
        resp = signup(client)
        assert resp.status_code == 200
        assert CODE.search(resp.text) and "ne sera plus affiché" in resp.text
        assert accounts.authenticate("alice", "mot-de-passe-1") == "alice"

    def test_signup_errors_keep_the_pseudo_and_escape_it(self, client):
        resp = signup(client, pseudo='"><script>x</script>')
        assert resp.status_code == 400
        assert "<script>" not in resp.text and "&lt;script&gt;" in resp.text

    def test_signup_with_different_passwords(self, client):
        resp = signup(client, confirm="autre-chose")
        assert resp.status_code == 400 and "pas identiques" in resp.text
        assert accounts.authenticate("alice", "mot-de-passe-1") is None

    def test_signup_with_a_taken_pseudo(self, client):
        signup(client)
        assert "déjà pris" in signup(client, pseudo="ALICE").text

    def test_recovery_flow(self, client):
        code = CODE.search(signup(client).text).group()
        resp = client.post(
            "/compte/recuperation",
            data={
                "pseudo": "alice",
                "code": code,
                "password": "nouveau-mot-de-passe",
                "confirm": "nouveau-mot-de-passe",
            },
        )
        assert resp.status_code == 200 and CODE.search(resp.text).group() != code
        assert accounts.authenticate("alice", "nouveau-mot-de-passe") == "alice"

    def test_recovery_with_a_wrong_code(self, client):
        signup(client)
        resp = client.post(
            "/compte/recuperation",
            data={
                "pseudo": "alice",
                "code": "AAAA-BBBB-CCCC-DDDD",
                "password": "nouveau-mot-de-passe",
                "confirm": "nouveau-mot-de-passe",
            },
        )
        assert resp.status_code == 400 and "incorrect" in resp.text

    def test_deletion_flow(self, client):
        signup(client)
        bad = client.post("/compte/suppression", data={"pseudo": "alice", "password": "mauvais"})
        assert bad.status_code == 400
        ok = client.post(
            "/compte/suppression", data={"pseudo": "alice", "password": "mot-de-passe-1"}
        )
        assert ok.status_code == 200 and "supprimés" in ok.text
        assert accounts.authenticate("alice", "mot-de-passe-1") is None

    def test_the_pages_are_rate_limited(self, client):
        statuses = [
            client.get("/compte/inscription").status_code
            for _ in range(settings.rate_limit_account + 1)
        ]
        assert statuses[-1] == 429 and set(statuses[:-1]) == {200}


class TestMount:
    def test_chat_is_not_mounted_without_a_secret(self, monkeypatch):
        monkeypatch.setattr(settings, "chainlit_auth_secret", "")
        app = FastAPI()
        before = list(app.routes)
        assert mount_chat(app) is False
        assert app.routes == before  # nothing added: the API keeps working

    def test_chat_is_mounted_on_the_api(self, client):
        from app.main import app

        assert app.state.chat_enabled is True
        assert getattr(app.routes[-1], "path", None) == ""  # Chainlit, last: it catches the rest
        assert client.get("/api/health").status_code in (200, 429)  # the API is untouched


class TestTheme:
    """The look is plain files in chat/public: a typo would only show in the browser."""

    PUBLIC = Path(__file__).resolve().parent.parent / "chat" / "public"

    def test_theme_colors_are_hsl_triplets(self):
        theme = json.loads((self.PUBLIC / "theme.json").read_text(encoding="utf-8"))
        for mode in theme["variables"].values():
            for name, value in mode.items():
                assert re.fullmatch(r"\d{1,3} \d{1,3}% \d{1,3}%", value), (name, value)

    @pytest.mark.parametrize(
        "name", ["logo_light.png", "logo_dark.png", "favicon.png", "login-bg.jpg", "login-links.js"]
    )
    def test_public_files_exist(self, name):
        assert (self.PUBLIC / name).stat().st_size > 0

    def test_the_assistant_avatar_file_matches_the_message_author(self):
        # chainlit/server.py get_avatar: lowercase, spaces and dots turned into "_"
        name = AUTHOR.lower().replace(" ", "_").replace(".", "_")
        assert any((self.PUBLIC / "avatars").glob(f"{name}.*"))

    def test_app_name_is_the_same_in_the_pages_and_in_the_config(self):
        config = (self.PUBLIC.parent / ".chainlit" / "config.toml").read_text(encoding="utf-8")
        assert f'name = "{pages.APP_NAME}"' in config

    def test_pages_carry_the_app_name(self, client):
        assert pages.APP_NAME in client.get("/compte/inscription").text
