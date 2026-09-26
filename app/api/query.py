"""Query endpoint with rate limiting."""

from fastapi import APIRouter, Depends, Request

from app.core.security import rate_limit_query
from app.schemas import QueryRequest, QueryResponse
from graph.builder import get_graph

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(rate_limit_query)])
async def query_rag(request: QueryRequest, _request: Request) -> QueryResponse:
    """
    Main RAG endpoint: question -> answer with sources.
    """
    graph = get_graph()
    initial_state = {"question": request.question}
    result = await graph.ainvoke(initial_state)

    return QueryResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        grade=result.get("grade", "refuse"),
    )
