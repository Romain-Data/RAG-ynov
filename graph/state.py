from typing import TypedDict

from app.schemas import Source


class GraphState(TypedDict, total=False):
    """State that flows through the LangGraph.

    total=False: each node returns only the keys it updates."""

    # Input
    question: str
    rewritten: str | None  # standalone version of a follow-up question (graph/chat.py)
    history: list[dict]  # previous messages {role, content}, chat graph only

    # Retrieval
    retrieved: list[dict]  # each: {text, score, source, page, section, ...}

    # Grading
    grade: str  # "ok" | "refuse"

    # Generation
    answer: str
    sources: list[Source]
    # What the LLM call reported (journal, #18): the model that really answered (the alias
    # may hide a change) and the tokens used
    llm_model: str | None
    tokens_in: int | None
    tokens_out: int | None
