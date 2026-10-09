"""Pytest fixtures. Env vars are set before app imports."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MAMMOUTH_API_KEY", "test-key")
os.environ.setdefault("INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("QDRANT_HOST", "localhost")
# Models asserted by the health test: set here so that it does not depend on a local .env
os.environ.setdefault("MAMMOUTH_CHAT_MODEL", "mistral-medium-3-5")
os.environ.setdefault(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
os.environ.setdefault("CHAINLIT_AUTH_SECRET", "test-secret-for-the-chat-tests")
os.environ.setdefault(
    "FAST_EMBED_CACHE_DIR",
    str(ROOT / ".fastembed_cache"),
)

# Import app AFTER setting env vars so lifespan doesn't hit Qdrant/FastEmbed
# ruff: noqa: E402
from app.main import app


# Replace lifespan with a no-op context manager
@asynccontextmanager
async def dummy_lifespan(_app):
    yield


app.router.lifespan_context = dummy_lifespan  # type: ignore


@pytest.fixture
def client() -> TestClient:
    """HTTP client with disabled lifespan."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(autouse=True)
def journal_db(tmp_path, monkeypatch):
    """Every test writes its journal entries to its own database, never to chat_data/."""
    from app.core.config import settings
    from chat.db import init_db

    monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "chat.db"))
    init_db()
