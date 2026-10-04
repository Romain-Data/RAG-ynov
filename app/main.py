from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api import health, ingest, query
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import add_security_middleware, rate_limit_health
from app.core.site_password import SitePasswordMiddleware
from chat.db import init_db
from chat.mount import mount_chat
from graph.builder import get_graph
from graph.chat import get_chat_graph
from ingestion.embedder import get_embedding_model
from ingestion.indexer import get_qdrant_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    setup_logging()
    # Initialize Qdrant client (validates connection)
    get_qdrant_client()
    # Warm up FastEmbed model (downloads ONNX if needed)
    get_embedding_model()
    # Compile LangGraph singletons
    get_graph()
    get_chat_graph()
    # Accounts and conversations of the chat (SQLite file)
    if app.state.chat_enabled:
        init_db()
    yield
    # Shutdown - nothing to close for these singletons


app = FastAPI(
    title="RAG Ynov",
    description="RAG pédagogique sur programmes Ynov + admissions",
    version="0.1.0",
    lifespan=lifespan,
)

# Security middleware (CORS + rate limiting)
add_security_middleware(app)

# Preprod only: a password in front of everything, added last so that it is the outermost
if settings.site_password:
    app.add_middleware(SitePasswordMiddleware, password=settings.site_password)

# Routers with rate limiting
app.include_router(health.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")

# Chat interface (Chainlit on /chat) and account pages, when CHAINLIT_AUTH_SECRET is set
app.state.chat_enabled = mount_chat(app)


@app.get("/", dependencies=[Depends(rate_limit_health)])
async def root() -> dict:
    return {
        "name": "RAG Ynov",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }
