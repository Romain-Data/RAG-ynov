"""Ingest endpoint with rate limiting."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import settings
from app.core.security import rate_limit_ingest
from app.schemas import IngestRequest, IngestResponse

router = APIRouter(tags=["ingest"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit_ingest)],
)
async def ingest_documents(
    _request: Request,
    request: IngestRequest,
    x_ingest_key: str | None = Header(None),
) -> IngestResponse:
    """
    Trigger document ingestion pipeline on data/ folder.

    Protected by X-Ingest-Key header for CLI-only access in V1.
    """
    if not x_ingest_key or x_ingest_key != settings.ingest_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing ingestion key",
        )

    # Import here to avoid circular imports
    from pathlib import Path

    from ingestion.run import ingest_directory

    data_dir = Path("data")
    if not data_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data directory not found",
        )

    count = ingest_directory(data_dir)
    return IngestResponse(
        status="ok" if count else "no_documents",
        indexed_chunks=count,
        collection=settings.qdrant_collection_name,
    )
