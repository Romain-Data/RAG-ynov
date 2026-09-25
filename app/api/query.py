from fastapi import APIRouter

from app.schemas import QueryRequest, QueryResponse
from graph.builder import get_graph

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest) -> QueryResponse:
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
