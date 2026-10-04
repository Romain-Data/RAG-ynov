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
