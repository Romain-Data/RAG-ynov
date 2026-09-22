from fastapi import APIRouter, HTTPException, status

from app.schemas import IngestRequest, IngestResponse

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_documents(request: IngestRequest) -> IngestResponse:
    """
    Trigger document ingestion pipeline.

    Note: In V1 this is a stub. The actual pipeline will be implemented
    in the ingestion/ module and called from here.
    """
    # TODO: Call ingestion pipeline
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Ingestion pipeline not yet implemented. Will be added in feat/ingestion branch.",
    )