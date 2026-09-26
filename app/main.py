from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request

from app.api import health, ingest, query
from app.core.logging import setup_logging
from app.core.security import add_security_middleware, rate_limit_health
from graph.builder import get_graph
from ingestion.embedder import get_embedding_model
from ingestion.indexer import get_qdrant_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    # Initialize Qdrant client (validates connection)
    get_qdrant_client()
    # Warm up FastEmbed model (downloads ONNX if needed)
    get_embedding_model()
    # Compile LangGraph singleton
    get_graph()
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

# Routers with rate limiting
app.include_router(health.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")


@app.get("/", dependencies=[Depends(rate_limit_health)])
async def root() -> dict:
    return {
        "name": "RAG Ynov",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }
