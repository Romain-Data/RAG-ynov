"""Tests for the accounts of the chat (no LLM, no network)."""
import re
import sqlite3

import pytest

from app.core.config import settings
from chat import accounts
from chat.db import db, init_db

CODE_RE = re.compile(r"^[A-Z2-9]{4}(-[A-Z2-9]{4}){3}$")


@pytest.fixture(autouse=True)
def chat_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "chat.db"))
    accounts._failures.clear()
    init_db()


class TestRegister:
    def test_returns_a_recovery_code_and_stores_only_hashes(self):
        code = accounts.register("alice", "mot-de-passe-1")
        assert CODE_RE.match(code)
        with db() as conn:
            row = conn.execute("SELECT * FROM accounts").fetchone()
        assert "mot-de-passe-1" not in str(row) and code not in str(row)
        assert row[1].startswith("$argon2") and row[2].startswith("$argon2")

    @pytest.mark.parametrize("pseudo", ["ab", "a" * 31, "with space", "é-accent", "a@b.com", ""])
    def test_rejects_invalid_pseudos(self, pseudo):
        with pytest.raises(accounts.AccountError, match="pseudo"):
            accounts.register(pseudo, "mot-de-passe-1")

    @pytest.mark.parametrize("password", ["", "short", "x" * 129])
    def test_rejects_invalid_passwords(self, password):
        with pytest.raises(accounts.AccountError, match="mot de passe"):
            accounts.register("alice", password)

    def test_pseudo_is_unique_whatever_the_case(self):
        accounts.register("Alice", "mot-de-passe-1")
        with pytest.raises(accounts.AccountError, match="déjà pris"):
            accounts.register("ALICE", "autre-mot-de-passe")


class TestAuthenticate:
    def test_returns_the_pseudo_as_stored(self):
        accounts.register("Alice", "mot-de-passe-1")
        assert accounts.authenticate("alice", "mot-de-passe-1") == "Alice"

    def test_wrong_password_and_unknown_pseudo_give_none(self):
        accounts.register("alice", "mot-de-passe-1")
        assert accounts.authenticate("alice", "mauvais") is None
        assert accounts.authenticate("bob", "mot-de-passe-1") is None

    def test_updates_the_last_login(self):
        accounts.register("alice", "mot-de-passe-1")
        accounts.authenticate("alice", "mot-de-passe-1")
        with db() as conn:
            assert conn.execute("SELECT last_login_at FROM accounts").fetchone()[0]

    def test_five_failures_block_the_pseudo_for_a_while(self, monkeypatch):
        accounts.register("alice", "mot-de-passe-1")
        for _ in range(accounts.MAX_FAILURES):
            assert accounts.authenticate("alice", "mauvais") is None
        # Even the right password is refused while blocked...
        assert accounts.authenticate("alice", "mot-de-passe-1") is None
        # ... and works again once the window has passed
        later = accounts.time.monotonic() + accounts.WINDOW_S + 1
        monkeypatch.setattr(accounts.time, "monotonic", lambda: later)
        assert accounts.authenticate("alice", "mot-de-passe-1") == "alice"


class TestRecover:
    def test_new_password_and_new_code(self):
        code = accounts.register("alice", "ancien-mot-de-passe")
        new_code = accounts.recover("alice", code.lower().replace("-", " "), "nouveau-mot-de-passe")
        assert CODE_RE.match(new_code) and new_code != code
        assert accounts.authenticate("alice", "ancien-mot-de-passe") is None
        assert accounts.authenticate("alice", "nouveau-mot-de-passe") == "alice"

    def test_a_code_works_only_once(self):
        code = accounts.register("alice", "ancien-mot-de-passe")
        accounts.recover("alice", code, "nouveau-mot-de-passe")
        with pytest.raises(accounts.AccountError, match="incorrect"):
            accounts.recover("alice", code, "encore-un-autre-mdp")

    def test_wrong_code_and_unknown_pseudo_give_the_same_error(self):
        accounts.register("alice", "mot-de-passe-1")
        for pseudo in ("alice", "bob"):
            with pytest.raises(accounts.AccountError, match="Pseudo ou code de secours incorrect"):
                accounts.recover(pseudo, "AAAA-BBBB-CCCC-DDDD", "nouveau-mot-de-passe")

    def test_guessing_codes_is_throttled(self):
        accounts.register("alice", "mot-de-passe-1")
        for _ in range(accounts.MAX_FAILURES):
            with pytest.raises(accounts.AccountError, match="incorrect"):
                accounts.recover("alice", "AAAA-BBBB-CCCC-DDDD", "nouveau-mot-de-passe")
        with pytest.raises(accounts.AccountError, match="Trop de tentatives"):
            accounts.recover("alice", "AAAA-BBBB-CCCC-DDDD", "nouveau-mot-de-passe")


class TestDeleteAccount:
    @staticmethod
    def _add_conversation(owner: str, thread_id: str) -> None:
        with db() as conn:
            conn.execute("INSERT INTO users (id, identifier, metadata) VALUES (?, ?, '{}')",
                         (f"u-{owner}", owner))
            conn.execute("INSERT INTO threads (id, userId, userIdentifier) VALUES (?, ?, ?)",
                         (thread_id, f"u-{owner}", owner))
            conn.execute(
                "INSERT INTO steps (id, name, type, threadId) VALUES (?, 'x', 'user_message', ?)",
                (f"s-{thread_id}", thread_id))
            conn.execute(
                "INSERT INTO feedbacks (id, forId, threadId, value) VALUES (?, 's', ?, 1)",
                (f"f-{thread_id}", thread_id))

    @staticmethod
    def _count(table: str) -> int:
        with db() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_removes_the_account_and_its_conversations_only(self):
        accounts.register("alice", "mot-de-passe-1")
        accounts.register("bob", "mot-de-passe-2")
        self._add_conversation("alice", "t-alice")
        self._add_conversation("bob", "t-bob")

        accounts.delete_account("alice", "mot-de-passe-1")

        assert accounts.authenticate("alice", "mot-de-passe-1") is None
        with db() as conn:
            assert conn.execute("SELECT id FROM threads").fetchall() == [("t-bob",)]
            assert conn.execute("SELECT id FROM users").fetchall() == [("u-bob",)]
        assert self._count("steps") == 1 and self._count("feedbacks") == 1
        assert accounts.authenticate("bob", "mot-de-passe-2") == "bob"

    def test_wrong_password_deletes_nothing(self):
        accounts.register("alice", "mot-de-passe-1")
        self._add_conversation("alice", "t-alice")
        with pytest.raises(accounts.AccountError, match="incorrect"):
            accounts.delete_account("alice", "mauvais")
        assert self._count("threads") == 1 and self._count("accounts") == 1


def test_init_db_is_idempotent_and_keeps_the_data():
    accounts.register("alice", "mot-de-passe-1")
    init_db()
    init_db()
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1


def test_chainlit_tables_have_the_columns_its_data_layer_writes():
    """The columns come from the pinned chainlit version: a bump must update schema.sql."""
    with db() as conn:
        steps = {row[1] for row in conn.execute("PRAGMA table_info(steps)")}
        threads = {row[1] for row in conn.execute("PRAGMA table_info(threads)")}
    assert {"defaultOpen", "autoCollapse", "showInput", "generation", "threadId"} <= steps
    assert {"userId", "userIdentifier", "createdAt", "name", "tags", "metadata"} <= threads
    assert sqlite3.sqlite_version_info >= (3, 24)  # ON CONFLICT ... DO UPDATE
