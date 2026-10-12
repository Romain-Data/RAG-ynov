"""SQLite file shared by the accounts and by Chainlit's data layer (threads, messages)."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings
from journal import gaps

logger = logging.getLogger(__name__)

SCHEMA = Path(__file__).with_name("schema.sql")

# Columns added to answer_log after its first release. schema.sql creates them on a new
# database; init_db adds them to an older one (there is no schema version: the columns tell).
ANSWER_LOG_ADDED_COLUMNS = {
    "feedback": "INTEGER CHECK (feedback IN (0, 1))",
    "feedback_comment": "TEXT",
    "feedback_at": "TEXT",
    # The theme of a question left without an answer (#20, table gap_theme)
    "gap_theme_id": "INTEGER",
}


def db_path() -> Path:
    return Path(settings.chat_db_path).resolve()


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """A connection that commits on success, rolls back on error and always closes. It knows
    gap_kind(route, answer, feedback), the kind of an entry left without an answer (#20)."""
    conn = sqlite3.connect(db_path(), timeout=10)
    gaps.register(conn)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(answer_log)")}
    missing = {name: decl for name, decl in ANSWER_LOG_ADDED_COLUMNS.items() if name not in columns}
    for name, decl in missing.items():
        conn.execute(f"ALTER TABLE answer_log ADD COLUMN {name} {decl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_answer_log_feedback ON answer_log (feedback)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_answer_log_gap_theme ON answer_log (gap_theme_id)")
    # Only the columns of the feedback (#19) have earlier data to copy
    if "feedback" in missing:
        from journal.store import backfill_feedback  # journal.store imports this module

        copied = backfill_feedback(conn)
        logger.info("answer_log: feedback columns added, %d earlier feedbacks copied", copied)
    if "gap_theme_id" in missing:
        logger.info("answer_log: gap_theme_id column added (themes of the unanswered questions)")


def init_db() -> None:
    """Create the folder, the tables and switch to WAL (readers do not block the writer)."""
    db_path().parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        _migrate(conn)


def sqlalchemy_url() -> str:
    return f"sqlite+aiosqlite:///{db_path()}"
