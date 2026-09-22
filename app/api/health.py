from fastapi import APIRouter, HTTPException
from httpx import AsyncClient

from app.core.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint that verifies API and Qdrant connectivity."""
    # Check Qdrant
    qdrant_status = "unreachable"
    qdrant_url = f"http://{settings.qdrant_host}:{settings.qdrant_port}"

    try:
        async with AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{qdrant_url}/healthz")
            if resp.status_code == 200:
                qdrant_status = "ok"
            else:
                qdrant_status = f"error:{resp.status_code}"
    except Exception:
        qdrant_status = "unreachable"

    overall_status = "ok" if qdrant_status == "ok" else "degraded"

    return HealthResponse(
        status=overall_status,
        qdrant=qdrant_status,
        embedding_model=settings.embedding_model,
        chat_model=settings.mammouth_chat_model,
    )