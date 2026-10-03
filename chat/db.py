"""SQLite file shared by the accounts and by Chainlit's data layer (threads, messages)."""
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings

SCHEMA = Path(__file__).with_name("schema.sql")


def db_path() -> Path:
    return Path(settings.chat_db_path).resolve()


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """A connection that commits on success, rolls back on error and always closes."""
    conn = sqlite3.connect(db_path(), timeout=10)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the folder, the tables and switch to WAL (readers do not block the writer)."""
    db_path().parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))


def sqlalchemy_url() -> str:
    return f"sqlite+aiosqlite:///{db_path()}"
