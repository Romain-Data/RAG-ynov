from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import health, query, ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    # TODO: Initialize Qdrant client, FastEmbed model, graph
    yield
    # Shutdown
    # TODO: Close connections


app = FastAPI(
    title="RAG Ynov",
    description="RAG pédagogique sur programmes Ynov + admissions",
    version="0.1.0",
    lifespan=lifespan,
)

# Routers
app.include_router(health.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "RAG Ynov",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }