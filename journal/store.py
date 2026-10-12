"""Write the journal of the answers (#18), copy the users' feedback into it (#19), purge it.

`record` and the feedback functions never raise: a journal that fails must not take an answer
(or a click on a thumb) down with it.
"""

import json
import logging
import os
import sqlite3
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from chat.db import db
from graph.nodes.grade import GRADE_THRESHOLD
from journal.redact import redact

logger = logging.getLogger(__name__)

MAX_TEXT = 4000  # the API caps a question at 2000 characters, the chat does not cap it
MAX_COMMENT = 1000  # the guard of PUT /feedback refuses longer comments (chat/feedback.py)
ROUTES = ("generate", "refuse", "smalltalk", "error")

# Chainlit ties a feedback to the `on_message` run, not to the answer: the answer is the run's
# child step, and its id is the message_id of the entry.
_ANSWER_OF_RUN = "message_id IN (SELECT id FROM steps WHERE parentId = :run_id)"


def route_of(result: dict | None, error: str | None) -> str:
    """How the graph ended: a generated answer, a refusal at the threshold, a fixed reply to
    a greeting, or an error."""
    if error or result is None:
        return "error"
    if result.get("grade") != "ok":
        return "refuse"
    return "generate" if result.get("retrieved") else "smalltalk"


def _hits(retrieved: list[dict]) -> list[dict]:
    """The search results without their text: what ranked where, not what was said."""
    return [
        {
            "source": r.get("source"),
            "section": r.get("section"),
            "page": r.get("page"),
            "score": round(r.get("score", 0.0), 4),
        }
        for r in retrieved
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def record(
    *,
    channel: str,
    question: str,
    result: dict | None = None,
    error: str | None = None,
    thread_id: str | None = None,
    message_id: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Add one entry. `result` is the final state of the graph, None when it raised."""
    if not settings.answer_log_enabled:
        return
    try:
        result = result or {}
        route = route_of(result or None, error)
        retrieved = result.get("retrieved") or []
        scores = [r.get("score", 0.0) for r in retrieved]
        rewritten = result.get("rewritten")
        row = {
            "created_at": _now(),
            "channel": channel,
            "thread_id": thread_id,
            "message_id": message_id,
            "question": redact(question)[:MAX_TEXT],
            "rewritten": redact(rewritten)[:MAX_TEXT] if rewritten else None,
            "answer": (result.get("answer") or "")[:MAX_TEXT],
            "route": route,
            "top_score": max(scores) if scores else None,
            "sources": json.dumps(result.get("sources") or [], ensure_ascii=False, default=str),
            "retrieved": json.dumps(_hits(retrieved), ensure_ascii=False),
            "llm_model": result.get("llm_model"),
            "llm_alias": settings.mammouth_chat_model if route in ("generate", "error") else None,
            "tokens_in": result.get("tokens_in"),
            "tokens_out": result.get("tokens_out"),
            "latency_ms": latency_ms,
            "error": error[:500] if error else None,
            "collection": settings.qdrant_collection_name,
            "embedding_model": settings.embedding_model,
            "threshold": GRADE_THRESHOLD,
            "app_version": os.environ.get("SOURCE_COMMIT") or None,
        }
        columns = ", ".join(row)
        marks = ", ".join(f":{name}" for name in row)
        with db() as conn:
            conn.execute(f"INSERT INTO answer_log ({columns}) VALUES ({marks})", row)
    except Exception:
        logger.exception("The answer could not be written to the journal")


def _comment(comment: str | None) -> str | None:
    comment = redact((comment or "").strip())[:MAX_COMMENT]
    return comment or None


def set_feedback(run_id: str, value: int, comment: str | None = None) -> int:
    """Copy a user's feedback (1 "Utile", 0 "Pas utile") to the entry of the answer it is
    about. Returns how many entries were updated: 0 when that answer is not in the journal."""
    if not settings.answer_log_enabled:
        return 0
    try:
        with db() as conn:
            return conn.execute(
                "UPDATE answer_log SET feedback = :value, feedback_comment = :comment, "
                f"feedback_at = :at WHERE {_ANSWER_OF_RUN}",
                {"value": value, "comment": _comment(comment), "at": _now(), "run_id": run_id},
            ).rowcount
    except Exception:
        logger.exception("The feedback could not be written to the journal")
        return 0


def clear_feedback(run_id: str) -> int:
    """The user took the feedback back (a second click on the same thumb)."""
    if not settings.answer_log_enabled:
        return 0
    try:
        with db() as conn:
            return conn.execute(
                "UPDATE answer_log SET feedback = NULL, feedback_comment = NULL, "
                f"feedback_at = NULL WHERE {_ANSWER_OF_RUN}",
                {"run_id": run_id},
            ).rowcount
    except Exception:
        logger.exception("The feedback could not be cleared from the journal")
        return 0


def backfill_feedback(conn: sqlite3.Connection) -> int:
    """Copy the feedback given before the journal kept it, once, when chat/db.py adds the
    columns. Its date is unknown: feedback_at stays empty. Returns how many entries got one."""
    try:
        found = conn.execute(
            "SELECT a.id, f.value, f.comment FROM answer_log a "
            "JOIN steps s ON s.id = a.message_id JOIN feedbacks f ON f.forId = s.parentId "
            "WHERE f.value IN (0, 1) ORDER BY f.rowid"
        ).fetchall()
        conn.executemany(
            "UPDATE answer_log SET feedback = ?, feedback_comment = ? WHERE id = ?",
            [(value, _comment(comment), entry_id) for entry_id, value, comment in found],
        )
        return len({entry_id for entry_id, _, _ in found})
    except Exception:
        logger.exception("The earlier feedback could not be copied to the journal")
        return 0


def purge(days: int | None = None) -> int:
    """Delete the entries older than `days` (default: ANSWER_LOG_RETENTION_DAYS). Returns how
    many were deleted."""
    days = settings.answer_log_retention_days if days is None else days
    if days < 1:
        raise ValueError("days must be at least 1")
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with db() as conn:
        deleted = conn.execute("DELETE FROM answer_log WHERE created_at < ?", (cutoff,)).rowcount
    return deleted
