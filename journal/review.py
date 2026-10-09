"""Read the journal and review its entries (the /admin pages, #18).

Kept apart from journal/store.py, which only writes.
"""

import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import yaml

from chat.db import db

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
REVIEW_LABELS = ("bonne", "partielle", "fausse", "hors_sujet")
MAX_NOTE = 1000
QUESTIONS_FILE = Path(__file__).resolve().parent.parent / "eval" / "questions.yaml"
_QUESTION_ID = re.compile(r"^q(\d+)$")


def _like(text: str) -> str:
    """A LIKE pattern matching `text` anywhere, with % and _ taken literally (ESCAPE '\\')."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_entries(
    *,
    review: str | None = None,
    route: str | None = None,
    channel: str | None = None,
    text: str | None = None,
    page: int = 1,
) -> tuple[list[dict], int]:
    """One page (PAGE_SIZE, newest first) of the entries that match the filters, and how many
    match in all. `review` is "unreviewed" or one of REVIEW_LABELS; an unknown value matches
    nothing rather than everything."""
    where: list[str] = []
    params: dict[str, object] = {}
    if review == "unreviewed":
        where.append("review_label IS NULL")
    elif review:
        where.append("review_label = :review")
        params["review"] = review
    if route:
        where.append("route = :route")
        params["route"] = route
    if channel:
        where.append("channel = :channel")
        params["channel"] = channel
    if text:
        where.append(
            "(question LIKE :text ESCAPE '\\' OR rewritten LIKE :text ESCAPE '\\' "
            "OR answer LIKE :text ESCAPE '\\')"
        )
        params["text"] = _like(text)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    params["limit"] = PAGE_SIZE
    params["offset"] = (max(page, 1) - 1) * PAGE_SIZE
    with db() as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute(f"SELECT COUNT(*) FROM answer_log {clause}", params).fetchone()[0]
        rows = conn.execute(
            "SELECT id, created_at, channel, question, route, top_score, llm_model, "
            f"review_label FROM answer_log {clause} ORDER BY id DESC LIMIT :limit OFFSET :offset",
            params,
        ).fetchall()
    return [dict(row) for row in rows], total


def _load_list(raw: str | None) -> list[dict]:
    try:
        loaded = json.loads(raw or "[]")
    except ValueError:
        return []
    return [item for item in loaded if isinstance(item, dict)] if isinstance(loaded, list) else []


def get_entry(entry_id: int) -> dict | None:
    """The full entry, its JSON columns decoded into `sources_list` and `retrieved_list`."""
    with db() as conn:
        conn.row_factory = sqlite3.Row
        found = conn.execute("SELECT * FROM answer_log WHERE id = ?", (entry_id,)).fetchone()
    if found is None:
        return None
    entry = dict(found)
    entry["sources_list"] = _load_list(entry["sources"])
    entry["retrieved_list"] = _load_list(entry["retrieved"])
    return entry


def next_unreviewed(entry_id: int) -> int | None:
    """The next older entry that has not been reviewed yet (the list runs newest first)."""
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM answer_log WHERE review_label IS NULL AND id < ? "
            "ORDER BY id DESC LIMIT 1",
            (entry_id,),
        ).fetchone()
    return int(row[0]) if row else None


def review(entry_id: int, label: str, note: str = "") -> bool:
    """Classify an entry. Returns False when it does not exist; raises ValueError on a label
    that is not one of REVIEW_LABELS."""
    if label not in REVIEW_LABELS:
        raise ValueError(f"unknown label: {label!r}")
    with db() as conn:
        updated = conn.execute(
            "UPDATE answer_log SET review_label = ?, review_note = ?, reviewed_at = ? WHERE id = ?",
            (label, note.strip()[:MAX_NOTE] or None, datetime.now(UTC).isoformat(), entry_id),
        ).rowcount
    return updated > 0


def mark_promoted(entry_id: int, question_id: str) -> bool:
    """Remember that the entry became `question_id` in eval/questions.yaml."""
    if not _QUESTION_ID.match(question_id):
        raise ValueError(f"not a question id: {question_id!r}")
    with db() as conn:
        updated = conn.execute(
            "UPDATE answer_log SET promoted_as = ? WHERE id = ?", (question_id, entry_id)
        ).rowcount
    return updated > 0


def next_question_id(questions_file: Path = QUESTIONS_FILE) -> str:
    """The id after the highest one in eval/questions.yaml and in the entries already
    promoted (whose pull request may not be merged yet)."""
    numbers: list[int] = []
    try:
        loaded = yaml.safe_load(questions_file.read_text(encoding="utf-8"))
        for item in loaded if isinstance(loaded, list) else []:
            match = _QUESTION_ID.match(str(item.get("id", "")))
            if match:
                numbers.append(int(match.group(1)))
    except (OSError, yaml.YAMLError):
        logger.warning("%s could not be read: the next question id is a guess", questions_file)
    with db() as conn:
        # IS NOT NULL: a bare "WHERE promoted_as" casts the text to a number and drops 'q40'
        for (promoted,) in conn.execute(
            "SELECT promoted_as FROM answer_log WHERE promoted_as IS NOT NULL"
        ):
            match = _QUESTION_ID.match(promoted)
            if match:
                numbers.append(int(match.group(1)))
    return f"q{max(numbers, default=0) + 1}"


def yaml_excerpt(entry: dict, question_id: str) -> str:
    """The entry as a question of eval/questions.yaml, to paste in a pull request. The facts
    expected in the answer (`answer_must`) are left for the reviewer to write. A follow-up is
    exported through its standalone rewrite, since the eval set has no conversation."""
    question = entry.get("rewritten") or entry["question"]
    lines = [f"- id: {question_id}", f"  question: {json.dumps(question, ensure_ascii=False)}"]
    if entry.get("review_label") == "hors_sujet" or entry["route"] == "refuse":
        lines.append("  out_of_scope: threshold  # llm if it passes the threshold and is declined")
        return "\n".join(lines) + "\n"
    expects: list[str] = []
    for src in entry.get("sources_list", []):
        if not src.get("source"):
            continue
        item = f"source: {json.dumps(src['source'], ensure_ascii=False)}"
        if src.get("section"):
            item += f", section: {json.dumps(src['section'], ensure_ascii=False)}"
        line = f"    - {{{item}}}"
        if line not in expects:
            expects.append(line)
    lines.append("  expect:" if expects else "  expect: []  # TODO: sections expected")
    lines += expects
    lines.append("  answer_must: []  # TODO: facts the answer must contain (regex)")
    return "\n".join(lines) + "\n"
