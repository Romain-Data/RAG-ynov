"""Tests for the journal of the answers (#18): what is written, masked, cleared and purged."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from chat import accounts
from chat.db import db
from graph.llm import LLMUnavailableError
from graph.nodes.grade import GRADE_THRESHOLD
from journal import store
from journal.redact import redact

GENERATED = {
    "question": "Combien coûte le BTS ?",
    "rewritten": "Combien coûte le BTS SIO ?",
    "grade": "ok",
    "answer": "8 900 € par an. [Source 1]",
    "sources": [{"source": "faq.md", "page": None, "section": "Tarifs", "score": 0.82}],
    "retrieved": [
        {"text": "long text", "source": "faq.md", "section": "Tarifs", "score": 0.82, "page": None},
        {"text": "other", "source": "faq.md", "section": "Admission", "score": 0.5, "page": None},
    ],
    "llm_model": "mistral-medium-3-5-2605",
    "tokens_in": 1200,
    "tokens_out": 80,
}
REFUSED = {"grade": "refuse", "answer": "Je n'ai pas trouvé...", "sources": [], "retrieved": []}
SMALLTALK = {"grade": "ok", "answer": "Bonjour !", "sources": [], "retrieved": []}


def rows() -> list[dict]:
    with db() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM answer_log ORDER BY id")]


class TestRedact:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("écris à jean.dupont+x@mail.fr merci", "écris à [e-mail] merci"),
            ("mon numéro 06 12 34 56 78 svp", "mon numéro [téléphone] svp"),
            ("+33 6 12 34 56 78", "[téléphone]"),
            ("06.12.34.56.78", "[téléphone]"),
            ("0612345678", "[téléphone]"),
        ],
    )
    def test_masks_what_identifies(self, text, expected):
        assert redact(text) == expected

    @pytest.mark.parametrize("text", ["8 900 € par an", "BTS en 2 ans, 120 ECTS", "le 12/10/2026"])
    def test_leaves_amounts_and_dates_alone(self, text):
        assert redact(text) == text


class TestRouteOf:
    def test_routes(self):
        assert store.route_of(GENERATED, None) == "generate"
        assert store.route_of(REFUSED, None) == "refuse"
        assert store.route_of(SMALLTALK, None) == "smalltalk"
        assert store.route_of(None, None) == "error"
        assert store.route_of(GENERATED, "boom") == "error"


class TestRecord:
    def test_a_generated_answer_keeps_everything_the_review_needs(self):
        store.record(
            channel="chat",
            question="Combien coûte le BTS ?",
            result=GENERATED,
            thread_id="t1",
            message_id="m1",
            latency_ms=1234,
        )
        (row,) = rows()
        assert row["route"] == "generate" and row["channel"] == "chat"
        assert row["answer"] == GENERATED["answer"]
        assert row["rewritten"] == "Combien coûte le BTS SIO ?"
        assert row["top_score"] == 0.82
        assert (row["thread_id"], row["message_id"], row["latency_ms"]) == ("t1", "m1", 1234)
        assert row["llm_model"] == "mistral-medium-3-5-2605"
        assert row["llm_alias"] == settings.mammouth_chat_model
        assert (row["tokens_in"], row["tokens_out"]) == (1200, 80)
        assert row["collection"] == settings.qdrant_collection_name
        assert row["embedding_model"] == settings.embedding_model
        assert row["threshold"] == GRADE_THRESHOLD
        assert json.loads(row["sources"])[0]["section"] == "Tarifs"
        hits = json.loads(row["retrieved"])
        assert [h["section"] for h in hits] == ["Tarifs", "Admission"]
        assert "text" not in hits[0]  # what ranked where, not the text of the corpus
        assert row["review_label"] is None and row["promoted_as"] is None

    def test_a_refusal_keeps_the_score_that_caused_it(self):
        refused = {**REFUSED, "retrieved": [{"source": "a", "score": 0.41}]}
        store.record(channel="api", question="Quel temps à Lyon ?", result=refused)
        (row,) = rows()
        assert row["route"] == "refuse" and row["top_score"] == 0.41
        assert row["llm_model"] is None and row["llm_alias"] is None
        assert row["thread_id"] is None

    def test_a_greeting_is_a_smalltalk(self):
        store.record(channel="chat", question="Bonjour", result=SMALLTALK)
        (row,) = rows()
        assert row["route"] == "smalltalk" and row["top_score"] is None

    def test_an_error_is_kept_with_its_cause(self):
        store.record(channel="api", question="Q ?", error="LLMUnavailableError: 429 budget")
        (row,) = rows()
        assert row["route"] == "error" and row["answer"] == ""
        assert row["error"] == "LLMUnavailableError: 429 budget"
        assert row["llm_alias"] == settings.mammouth_chat_model

    def test_the_question_is_masked_before_it_is_written(self):
        store.record(
            channel="chat",
            question="Je suis jean@mail.fr, rappelez-moi au 06 12 34 56 78",
            result={**GENERATED, "rewritten": "Appeler jean@mail.fr ?"},
        )
        (row,) = rows()
        assert row["question"] == "Je suis [e-mail], rappelez-moi au [téléphone]"
        assert row["rewritten"] == "Appeler [e-mail] ?"

    def test_long_texts_are_cut(self):
        store.record(channel="chat", question="x" * 10000, result=GENERATED)
        assert len(rows()[0]["question"]) == store.MAX_TEXT

    def test_it_can_be_switched_off(self, monkeypatch):
        monkeypatch.setattr(settings, "answer_log_enabled", False)
        store.record(channel="chat", question="Q ?", result=GENERATED)
        assert rows() == []

    def test_a_broken_journal_never_raises(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "chat_db_path", "/nonexistent-folder/chat.db")
        store.record(channel="chat", question="Q ?", result=GENERATED)  # must not raise
        assert "could not be written" in caplog.text


class TestPurge:
    @staticmethod
    def _age(entry_id: int, days: int) -> None:
        old = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with db() as conn:
            conn.execute("UPDATE answer_log SET created_at = ? WHERE id = ?", (old, entry_id))

    def test_deletes_only_what_is_past_the_retention(self):
        for _ in range(3):
            store.record(channel="api", question="Q ?", result=GENERATED)
        self._age(1, 181)
        self._age(2, 179)
        assert store.purge() == 1
        assert [r["id"] for r in rows()] == [2, 3]

    def test_days_can_be_given(self):
        store.record(channel="api", question="Q ?", result=GENERATED)
        self._age(1, 10)
        assert store.purge(days=7) == 1

    def test_refuses_a_retention_that_would_empty_the_journal(self):
        with pytest.raises(ValueError):
            store.purge(days=0)


class TestAccountDeletion:
    def test_the_entries_stay_but_lose_their_conversation(self):
        accounts.register("alice", "mot-de-passe-1")
        accounts.register("bob", "mot-de-passe-2")
        with db() as conn:
            for owner in ("alice", "bob"):
                conn.execute(
                    "INSERT INTO threads (id, userId, userIdentifier) VALUES (?, ?, ?)",
                    (f"t-{owner}", f"u-{owner}", owner),
                )
        store.record(
            channel="chat",
            question="Q alice",
            result=GENERATED,
            thread_id="t-alice",
            message_id="m1",
        )
        store.record(
            channel="chat", question="Q bob", result=GENERATED, thread_id="t-bob", message_id="m2"
        )

        accounts.delete_account("alice", "mot-de-passe-1")

        alice, bob = rows()
        assert alice["question"] == "Q alice"
        assert (alice["thread_id"], alice["message_id"]) == (None, None)
        assert (bob["thread_id"], bob["message_id"]) == ("t-bob", "m2")


class TestEndpoints:
    @patch("app.api.query.get_graph")
    def test_query_writes_one_entry(self, mock_get_graph, client):
        graph = AsyncMock()
        graph.ainvoke.return_value = GENERATED
        mock_get_graph.return_value = graph
        assert client.post("/api/query", json={"question": "Combien ?"}).status_code == 200
        (row,) = rows()
        assert row["channel"] == "api" and row["question"] == "Combien ?"
        assert row["route"] == "generate" and row["thread_id"] is None
        assert row["latency_ms"] is not None

    @patch("app.api.query.get_graph")
    def test_query_still_answers_when_the_journal_is_broken(self, mock_get_graph, client):
        graph = AsyncMock()
        graph.ainvoke.return_value = GENERATED
        mock_get_graph.return_value = graph
        with patch("journal.store.db", side_effect=OSError("disk full")):
            resp = client.post("/api/query", json={"question": "Combien ?"})
        assert resp.status_code == 200 and resp.json()["answer"] == GENERATED["answer"]

    @patch("app.api.query.get_graph")
    def test_a_llm_outage_is_kept_as_an_error(self, mock_get_graph, client):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(side_effect=LLMUnavailableError("429 budget"))
        mock_get_graph.return_value = graph
        assert client.post("/api/query", json={"question": "Combien ?"}).status_code == 503
        (row,) = rows()
        assert row["route"] == "error" and "429 budget" in row["error"]


@patch("graph.llm.httpx.Client")
def test_generate_node_reports_the_real_model_and_the_tokens(mock_httpx_cls):
    from graph.nodes.generate import generate_node

    resp = MagicMock()
    resp.json.return_value = {
        "model": "mistral-medium-3-5-2605",
        "choices": [{"message": {"content": "Réponse"}}],
        "usage": {"prompt_tokens": 900, "completion_tokens": 40},
    }
    mock_httpx_cls.return_value.__enter__.return_value.post.return_value = resp
    result = generate_node(
        {"question": "Q ?", "retrieved": [{"text": "t", "source": "a.md", "score": 0.9}]}
    )
    assert result["llm_model"] == "mistral-medium-3-5-2605"
    assert (result["tokens_in"], result["tokens_out"]) == (900, 40)


class TestChatHandler:
    """chat/app.py:on_message with Chainlit's session, message and graph replaced."""

    @staticmethod
    def _run(graph) -> list[MagicMock]:
        import asyncio

        from chat import app as chat_app

        sent: list[MagicMock] = []

        def make_message(**kwargs):
            msg = MagicMock(**kwargs)
            msg.id = f"m{len(sent) + 1}"
            msg.send = AsyncMock()
            sent.append(msg)
            return msg

        question = MagicMock(content="Je m'appelle jean@mail.fr, combien coûte le BTS ?")
        with (
            patch.object(chat_app, "get_chat_graph", return_value=graph),
            patch.object(chat_app.cl, "Message", side_effect=make_message),
            patch.object(chat_app.cl, "user_session", MagicMock(get=lambda _k: [])),
            patch.object(chat_app.cl, "context", MagicMock(session=MagicMock(thread_id="t-1"))),
        ):
            asyncio.run(chat_app.on_message(question))
        return sent

    def test_an_answer_is_kept_with_its_conversation_and_message(self):
        graph = MagicMock(ainvoke=AsyncMock(return_value=GENERATED))
        sent = self._run(graph)
        (row,) = rows()
        assert row["channel"] == "chat" and row["route"] == "generate"
        assert row["question"].startswith("Je m'appelle [e-mail]")
        assert (row["thread_id"], row["message_id"]) == ("t-1", sent[-1].id)

    def test_a_failure_is_kept_and_the_user_still_gets_a_message(self):
        graph = MagicMock(ainvoke=AsyncMock(side_effect=LLMUnavailableError("429 budget")))
        sent = self._run(graph)
        (row,) = rows()
        assert row["route"] == "error" and "429 budget" in row["error"]
        assert row["thread_id"] == "t-1" and row["message_id"] is None
        assert len(sent) == 1
