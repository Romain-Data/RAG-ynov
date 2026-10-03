"""Backup of the chat database (accounts and conversations).

    python -m chat.backup [--dir DIR] [--keep N]

Makes a consistent copy of the SQLite file with SQLite's own backup API (a plain `cp`
could miss what is still in the WAL), checks the copy, then keeps only the N newest
copies. Meant to run daily (a scheduled task in Coolify, inside the api container).
The folder should live outside the Docker volume that holds the database, so that
losing the volume does not lose the copies.
"""
import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from chat.db import db_path

PREFIX = "chat-"
SUFFIX = ".db"


def backup(dest_dir: Path, keep: int, now: datetime | None = None) -> Path:
    """Copy the chat database into `dest_dir`, check it, prune the old copies."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    source = db_path()
    if not source.exists():
        raise FileNotFoundError(f"no chat database at {source}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    target = dest_dir / f"{PREFIX}{stamp}{SUFFIX}"
    partial = target.with_suffix(".partial")  # never leave a half-written copy under a real name

    src = sqlite3.connect(source, timeout=30)
    dst = sqlite3.connect(partial)
    try:
        src.backup(dst)
        result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dst.close()
        src.close()
    if result != "ok":
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"the copy failed its integrity check: {result}")
    partial.replace(target)

    for old in sorted(dest_dir.glob(f"{PREFIX}*{SUFFIX}"), reverse=True)[keep:]:
        old.unlink()
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=Path(settings.chat_backup_dir))
    parser.add_argument("--keep", type=int, default=settings.chat_backup_keep)
    args = parser.parse_args()
    target = backup(args.dir, args.keep)
    count = len(list(args.dir.glob(f"{PREFIX}*{SUFFIX}")))
    print(f"backup written: {target} ({target.stat().st_size} bytes), {count} kept")


if __name__ == "__main__":
    main()
