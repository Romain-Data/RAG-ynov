"""Tests for the backup of the chat database (no LLM, no network)."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from chat import accounts
from chat.backup import backup
from chat.db import init_db

T0 = datetime(2026, 10, 4, 3, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def chat_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "chat.db"))
    accounts._failures.clear()
    init_db()
    accounts.register("alice", "mot-de-passe-1")


def test_the_copy_is_a_working_database_with_the_accounts(tmp_path):
    target = backup(tmp_path / "backups", keep=3, now=T0)
    assert target.name == "chat-20261004-030000.db"
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT pseudo FROM accounts").fetchall() == [("alice",)]
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_what_is_still_in_the_wal_is_in_the_copy(tmp_path):
    # An open connection that wrote but did not checkpoint: a plain file copy would miss it
    writer = sqlite3.connect(settings.chat_db_path)
    writer.execute("INSERT INTO accounts VALUES ('bob', 'h', 'h', '2026-10-04', NULL)")
    writer.commit()
    try:
        target = backup(tmp_path / "backups", keep=3, now=T0)
    finally:
        writer.close()
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone() == (2,)


def test_only_the_newest_copies_are_kept(tmp_path):
    dest = tmp_path / "backups"
    for day in range(5):
        backup(dest, keep=3, now=T0 + timedelta(days=day))
    names = sorted(p.name for p in dest.iterdir())
    assert names == [
        "chat-20261006-030000.db",
        "chat-20261007-030000.db",
        "chat-20261008-030000.db",
    ]


def test_no_partial_file_is_left_behind(tmp_path):
    backup(tmp_path / "backups", keep=3, now=T0)
    assert not list((tmp_path / "backups").glob("*.partial"))


def test_missing_database_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "nothing.db"))
    with pytest.raises(FileNotFoundError):
        backup(tmp_path / "backups", keep=3, now=T0)


def test_keep_must_be_positive(tmp_path):
    with pytest.raises(ValueError):
        backup(tmp_path / "backups", keep=0, now=T0)
