"""Write the journal of the answers (#18) and purge it.

`record` never raises: a journal that fails must not take an answer down with it.
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from chat.db import db
from graph.nodes.grade import GRADE_THRESHOLD
from journal.redact import redact

logger = logging.getLogger(__name__)

MAX_TEXT = 4000  # the API caps a question at 2000 characters, the chat does not cap it
ROUTES = ("generate", "refuse", "smalltalk", "error")


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
