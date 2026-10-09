"""Query endpoint with rate limiting."""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.security import rate_limit_query
from app.schemas import QueryRequest, QueryResponse
from graph.builder import get_graph
from graph.llm import LLMUnavailableError
from journal import store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(rate_limit_query)])
async def query_rag(request: QueryRequest, _request: Request) -> QueryResponse:
    """
    Main RAG endpoint: question -> answer with sources.
    """
    graph = get_graph()
    initial_state = {"question": request.question}
    started = time.monotonic()
    try:
        result = await graph.ainvoke(initial_state)
    except LLMUnavailableError as exc:
        logger.error("The LLM is unavailable: %s", exc)
        await asyncio.to_thread(
            store.record,
            channel="api",
            question=request.question,
            error=f"{type(exc).__name__}: {exc}",
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de génération est momentanément indisponible, réessayez.",
            headers={"Retry-After": "10"},
        ) from exc

    await asyncio.to_thread(
        store.record,
        channel="api",
        question=request.question,
        result=dict(result),
        latency_ms=round((time.monotonic() - started) * 1000),
    )
    return QueryResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        grade=result.get("grade", "refuse"),
    )
