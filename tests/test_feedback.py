"""Tests for the thumbs under the answers (#19): copied to the journal, guarded, migrated."""

import asyncio
import logging
import secrets
import sqlite3

import chainlit.data
import pytest
from chainlit.auth import create_jwt
from chainlit.types import Feedback
from chainlit.user import User
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app import main
from app.core.config import settings
from app.core.security import add_security_middleware, limiter
from chat import accounts
from chat.db import SCHEMA, db, init_db, sqlalchemy_url
from chat.feedback import FeedbackDataLayer
from chat.feedback import router as feedback_router
from journal import store

GENERATED = {"grade": "ok", "answer": "8 900 € par an.", "sources": [], "retrieved": []}


@pytest.fixture(autouse=True)
def fresh_state():
    """No request count and no data layer left by another test (Chainlit caches the data
    layer, bound to the database of the test that created it)."""
    limiter.reset()
    chainlit.data._data_layer = None
    chainlit.data._data_layer_initialized = False
    yield
    chainlit.data._data_layer = None
    chainlit.data._data_layer_initialized = False


def conversation(owner: str, n: int = 1) -> dict[str, str]:
    """A thread of `owner` with one exchange as Chainlit stores it, and its journal entry."""
    ids = {
        "thread": f"t-{owner}",
        "question": f"q-{owner}-{n}",
        "run": f"r-{owner}-{n}",
        "answer": f"a-{owner}-{n}",
        "start": f"start-{owner}",
    }
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO threads (id, userId, userIdentifier) VALUES (?, ?, ?)",
            (ids["thread"], f"u-{owner}", owner),
        )
        conn.execute(
            "INSERT OR IGNORE INTO steps (id, name, type, threadId) "
            "VALUES (?, 'on_chat_start', 'run', ?)",
            (ids["start"], ids["thread"]),
        )
        for step_id, name, kind, parent in (
            (ids["question"], owner, "user_message", None),
            (ids["run"], "on_message", "run", ids["question"]),
            (ids["answer"], "Chatbot Ynov", "assistant_message", ids["run"]),
        ):
            conn.execute(
                "INSERT INTO steps (id, name, type, threadId, parentId) VALUES (?, ?, ?, ?, ?)",
                (step_id, name, kind, ids["thread"], parent),
            )
    store.record(
        channel="chat",
        question=f"Question {n} de {owner}",
        result=GENERATED,
        thread_id=ids["thread"],
        message_id=ids["answer"],
    )
    return ids


def entry(message_id: str) -> dict:
    with db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM answer_log WHERE message_id = ?", (message_id,))
        return dict(row.fetchone())


def feedbacks() -> list[tuple]:
    with db() as conn:
        return conn.execute(
            "SELECT id, forId, threadId, value, comment FROM feedbacks ORDER BY rowid"
        ).fetchall()


class TestStore:
    def test_a_thumb_is_copied_to_the_entry_of_the_answer(self):
        ids = conversation("alice")
        assert store.set_feedback(ids["run"], 1) == 1
        row = entry(ids["answer"])
        assert (row["feedback"], row["feedback_comment"]) == (1, None)
        assert row["feedback_at"]

    def test_a_change_of_mind_keeps_the_comment_masked_and_cut(self):
        ids = conversation("alice")
        store.set_feedback(ids["run"], 1)
        comment = "Écrivez-moi à jean@mail.fr " + "x" * 2000
        store.set_feedback(ids["run"], 0, comment)
        row = entry(ids["answer"])
        assert row["feedback"] == 0
        assert row["feedback_comment"].startswith("Écrivez-moi à [e-mail] x")
        assert len(row["feedback_comment"]) == store.MAX_COMMENT

    def test_a_blank_comment_is_no_comment(self):
        ids = conversation("alice")
        store.set_feedback(ids["run"], 0, "   ")
        assert entry(ids["answer"])["feedback_comment"] is None

    def test_taking_it_back_clears_it(self):
        ids = conversation("alice")
        store.set_feedback(ids["run"], 0, "Il manque le prix")
        assert store.clear_feedback(ids["run"]) == 1
        row = entry(ids["answer"])
        assert (row["feedback"], row["feedback_comment"], row["feedback_at"]) == (None, None, None)

    def test_only_the_answer_of_that_run_gets_it(self):
        first, second = conversation("alice", 1), conversation("alice", 2)
        store.set_feedback(second["run"], 1)
        assert entry(first["answer"])["feedback"] is None
        assert entry(second["answer"])["feedback"] == 1

    def test_an_unknown_run_changes_nothing(self):
        ids = conversation("alice")
        assert store.set_feedback("unknown", 1) == 0
        assert store.clear_feedback("unknown") == 0
        assert entry(ids["answer"])["feedback"] is None

    def test_nothing_is_written_when_the_journal_is_off(self, monkeypatch):
        ids = conversation("alice")
        monkeypatch.setattr(settings, "answer_log_enabled", False)
        assert store.set_feedback(ids["run"], 1) == 0
        monkeypatch.setattr(settings, "answer_log_enabled", True)
        assert entry(ids["answer"])["feedback"] is None

    def test_a_broken_journal_never_raises(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "chat_db_path", "/nonexistent-folder/chat.db")
        with caplog.at_level(logging.ERROR):
            assert store.set_feedback("r", 1) == 0
            assert store.clear_feedback("r") == 0
        assert "could not be" in caplog.text


class TestDataLayer:
    """What Chainlit's PUT and DELETE /feedback call once the guard has let them through."""

    @staticmethod
    def _run(coro_factory):
        async def go():
            layer = FeedbackDataLayer(conninfo=sqlalchemy_url())
            try:
                return await coro_factory(layer)
            finally:
                await layer.engine.dispose()

        return asyncio.run(go())

    def test_upsert_writes_chainlit_table_and_the_journal(self):
        ids = conversation("alice")
        feedback = Feedback(forId=ids["run"], threadId=ids["thread"], value=0, comment="Faux")
        feedback_id = self._run(lambda layer: layer.upsert_feedback(feedback))
        assert feedbacks() == [(feedback_id, ids["run"], ids["thread"], 0, "Faux")]
        assert (entry(ids["answer"])["feedback"], entry(ids["answer"])["feedback_comment"]) == (
            0,
            "Faux",
        )

    def test_delete_removes_it_from_both(self):
        ids = conversation("alice")
        feedback = Feedback(forId=ids["run"], threadId=ids["thread"], value=1)

        async def upsert_then_delete(layer):
            feedback_id = await layer.upsert_feedback(feedback)
            return await layer.delete_feedback(feedback_id)

        assert self._run(upsert_then_delete) is True
        assert feedbacks() == []
        assert entry(ids["answer"])["feedback"] is None

    def test_deleting_an_unknown_feedback_is_harmless(self):
        ids = conversation("alice")
        store.set_feedback(ids["run"], 1)
        self._run(lambda layer: layer.delete_feedback("unknown"))
        assert entry(ids["answer"])["feedback"] == 1


@pytest.fixture
def client():
    """The guard routes, then a catch-all mounted on / like Chainlit (chat/mount.py)."""
    catch_all = Starlette(routes=[Route("/{path:path}", lambda _r: PlainTextResponse("chat"))])
    app = FastAPI()
    add_security_middleware(app)
    app.include_router(feedback_router)
    app.mount("/", catch_all)
    with TestClient(app) as c:
        yield c


def auth(pseudo: str) -> dict[str, str]:
    token = create_jwt(User(identifier=pseudo, metadata={"provider": "credentials"}))
    return {"Authorization": f"Bearer {token}"}


def put(client, pseudo, ids, value=1, comment=None, **overrides):
    feedback = {"forId": ids["run"], "threadId": ids["thread"], "value": value}
    if comment is not None:
        feedback["comment"] = comment
    feedback.update(overrides)
    return client.put(
        "/feedback",
        json={"feedback": feedback, "sessionId": "s-1"},
        headers=auth(pseudo) if pseudo else {},
    )


def delete(client, pseudo, feedback_id):
    return client.request(
        "DELETE", "/feedback", json={"feedbackId": feedback_id}, headers=auth(pseudo)
    )


class TestGuard:
    def test_the_owner_gives_a_thumb(self, client):
        ids = conversation("alice")
        resp = put(client, "alice", ids, value=1)
        assert resp.status_code == 200 and resp.json()["success"] is True
        ((feedback_id, for_id, thread_id, value, _),) = feedbacks()
        assert (feedback_id, for_id, thread_id, value) == (
            resp.json()["feedbackId"],
            ids["run"],
            ids["thread"],
            1,
        )
        assert entry(ids["answer"])["feedback"] == 1

    def test_the_routes_answer_before_the_chat(self, client):
        assert client.get("/autre").text == "chat"  # the catch-all is really there
        assert put(client, None, conversation("alice")).status_code == 401

    def test_a_second_thumb_updates_the_first(self, client):
        ids = conversation("alice")
        first = put(client, "alice", ids, value=1).json()["feedbackId"]
        second = put(client, "alice", ids, value=0, comment="Il manque la durée").json()
        assert second["feedbackId"] == first
        assert len(feedbacks()) == 1
        row = entry(ids["answer"])
        assert (row["feedback"], row["feedback_comment"]) == (0, "Il manque la durée")

    def test_an_id_sent_by_the_browser_cannot_rewrite_another_feedback(self, client):
        alice, bob = conversation("alice"), conversation("bob")
        bobs = put(client, "bob", bob, value=1).json()["feedbackId"]
        resp = put(client, "alice", alice, value=0, id=bobs)
        assert resp.status_code == 200 and resp.json()["feedbackId"] != bobs
        assert {row[1]: row[3] for row in feedbacks()} == {bob["run"]: 1, alice["run"]: 0}
        assert entry(bob["answer"])["feedback"] == 1

    def test_without_a_session(self, client):
        assert put(client, None, conversation("alice")).status_code == 401
        assert feedbacks() == []

    def test_another_users_answer(self, client):
        ids = conversation("alice")
        assert put(client, "bob", ids).status_code == 404
        assert feedbacks() == [] and entry(ids["answer"])["feedback"] is None

    @pytest.mark.parametrize("step", ["answer", "question", "start", "unknown"])
    def test_only_the_run_of_a_message_can_be_rated(self, client, step):
        ids = conversation("alice")
        resp = put(client, "alice", ids, forId=ids.get(step, "unknown"))
        assert resp.status_code == 404 and feedbacks() == []

    def test_the_thread_must_be_the_one_of_the_run(self, client):
        alice_1 = conversation("alice")
        with db() as conn:
            conn.execute("INSERT INTO threads (id, userIdentifier) VALUES ('t-other', 'alice')")
        assert put(client, "alice", alice_1, threadId="t-other").status_code == 404

    def test_a_comment_too_long_is_refused(self, client):
        ids = conversation("alice")
        resp = put(client, "alice", ids, value=0, comment="x" * (store.MAX_COMMENT + 1))
        assert resp.status_code == 422 and feedbacks() == []

    def test_a_value_other_than_0_or_1_is_refused(self, client):
        assert put(client, "alice", conversation("alice"), value=5).status_code == 422

    def test_the_owner_takes_it_back(self, client):
        ids = conversation("alice")
        feedback_id = put(client, "alice", ids, value=0, comment="Faux").json()["feedbackId"]
        assert delete(client, "alice", feedback_id).status_code == 200
        assert feedbacks() == [] and entry(ids["answer"])["feedback"] is None

    def test_nobody_else_can_take_it_back(self, client):
        ids = conversation("alice")
        feedback_id = put(client, "alice", ids).json()["feedbackId"]
        assert delete(client, "bob", feedback_id).status_code == 404
        assert delete(client, "alice", "unknown").status_code == 404
        assert len(feedbacks()) == 1 and entry(ids["answer"])["feedback"] == 1

    def test_thumbs_are_rate_limited(self, client):
        ids = conversation("alice")
        codes = [
            put(client, "alice", ids, value=n % 2).status_code
            for n in range(settings.rate_limit_feedback + 1)
        ]
        assert codes[0] == 200 and codes[-1] == 429


def test_the_main_app_guards_chainlit_feedback_routes():
    """Chainlit, mounted on /, answers every path declared before it does not: without the guard
    first, its own PUT /feedback would store a thumb on a step that does not exist."""
    with TestClient(main.app) as c:
        resp = c.put(
            "/feedback",
            json={"feedback": {"forId": "nothing", "value": 1}, "sessionId": "s"},
            headers=auth("alice"),
        )
    assert resp.status_code == 404 and resp.json()["detail"] == "Réponse introuvable"
    assert feedbacks() == []


class TestMigration:
    @staticmethod
    def _old_database() -> None:
        """The schema before #19: answer_log without the feedback columns."""
        schema = SCHEMA.read_text(encoding="utf-8")
        start = schema.index("    promoted_as TEXT,")
        end = schema.index(");", start)
        old = schema[:start] + "    promoted_as TEXT\n" + schema[end:]
        assert "feedback INTEGER" not in old
        with sqlite3.connect(settings.chat_db_path) as conn:
            conn.executescript(old)

    @staticmethod
    def _columns() -> set[str]:
        with db() as conn:
            return {row[1] for row in conn.execute("PRAGMA table_info(answer_log)")}

    @staticmethod
    def _indexes() -> set[str]:
        with db() as conn:
            return {row[1] for row in conn.execute("PRAGMA index_list(answer_log)")}

    def test_a_new_database_has_the_columns_and_their_index(self):
        assert {"feedback", "feedback_comment", "feedback_at"} <= self._columns()
        assert "idx_answer_log_feedback" in self._indexes()

    def test_an_older_database_gets_them_with_the_earlier_feedback(
        self, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "old.db"))
        self._old_database()
        with db() as conn:
            conn.execute(
                "INSERT INTO answer_log (created_at, channel, thread_id, message_id, question, "
                "answer, route, collection, embedding_model, threshold) VALUES "
                "('2026-10-10', 'chat', 't', ?, 'Q', 'R', 'generate', 'c', 'm', 0.47)",
                ("answer-1",),
            )
            conn.executemany(
                "INSERT INTO steps (id, name, type, threadId, parentId) VALUES (?, ?, ?, 't', ?)",
                [
                    ("run-1", "on_message", "run", None),
                    ("answer-1", "x", "assistant_message", "run-1"),
                ],
            )
            conn.execute(
                "INSERT INTO feedbacks (id, forId, threadId, value, comment) "
                "VALUES ('f-1', 'run-1', 't', 0, 'Appelez le 06 12 34 56 78')"
            )
            conn.execute(
                "INSERT INTO feedbacks (id, forId, threadId, value) VALUES ('f-2', 'gone', 't', 1)"
            )

        with caplog.at_level(logging.INFO, logger="chat.db"):
            init_db()

        assert {"feedback", "feedback_comment", "feedback_at"} <= self._columns()
        assert "idx_answer_log_feedback" in self._indexes()
        row = entry("answer-1")
        assert (row["feedback"], row["feedback_comment"], row["feedback_at"]) == (
            0,
            "Appelez le [téléphone]",
            None,
        )
        assert "1 earlier feedbacks copied" in caplog.text

        caplog.clear()
        with caplog.at_level(logging.INFO, logger="chat.db"):
            init_db()  # idempotent: nothing to add, nothing copied again
        assert "copied" not in caplog.text
        assert entry("answer-1")["feedback"] == 0


def test_deleting_an_account_keeps_its_feedback_in_the_journal_only():
    password = secrets.token_urlsafe(12)
    accounts.register("alice", password)
    ids = conversation("alice")
    with db() as conn:
        conn.execute(
            "INSERT INTO feedbacks (id, forId, threadId, value, comment) VALUES (?, ?, ?, ?, ?)",
            ("f-1", ids["run"], ids["thread"], 0, "Non"),
        )
    store.set_feedback(ids["run"], 0, "Non")

    accounts.delete_account("alice", password)

    assert feedbacks() == []
    with db() as conn:
        row = conn.execute(
            "SELECT thread_id, message_id, feedback, feedback_comment FROM answer_log"
        ).fetchone()
    assert row == (None, None, 0, "Non")
