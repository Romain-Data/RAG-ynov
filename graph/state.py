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
