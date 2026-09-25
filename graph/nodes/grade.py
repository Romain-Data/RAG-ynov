from graph.state import GraphState


def grade_node(state: GraphState) -> GraphState:
    """Grade retrieved documents: are they relevant enough?"""
    # TODO: Simple threshold on Qdrant score first
    # Later: LLM-as-judge for finer grading
    retrieved = state.get("retrieved", [])
    if not retrieved:
        return {"grade": "refuse"}

    # Simple threshold: max score >= 0.5 (cosine similarity)
    max_score = max((r.get("score", 0) for r in retrieved), default=0)
    grade = "ok" if max_score >= 0.5 else "refuse"
    return {"grade": grade}