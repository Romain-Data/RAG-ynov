from fastapi import APIRouter, HTTPException, Depends, status
from app.core.config import settings
from app.schemas import QueryRequest, QueryResponse
from app.graph.builder import get_graph  # to be created later

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest) -> QueryResponse:
    """
    Main RAG endpoint: question -> answer with sources.
    """
    # TODO: Implement using LangGraph
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="RAG query pipeline not yet implemented. Will be added in feat/graph and feat/api branches.",
    )