from typing import TypedDict, List, Optional
from app.schemas import Source


class GraphState(TypedDict):
    """State that flows through the LangGraph."""
    # Input
    question: str
    rewritten: Optional[str]  # standalone version of a follow-up question (graph/chat.py)
    history: List[dict]  # previous messages {role, content}, chat graph only

    # Retrieval
    retrieved: List[dict]  # each: {text, score, source, page, section, ...}

    # Grading
    grade: str  # "ok" | "refuse"

    # Generation
    answer: str
    sources: List[Source]