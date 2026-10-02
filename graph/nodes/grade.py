from graph.state import GraphState

# Minimum top cosine score to answer; below it the question is refused without calling
# the LLM. Also used by eval/ to flag questions that would be refused.
GRADE_THRESHOLD = 0.5


def grade_node(state: GraphState) -> GraphState:
    """Grade retrieved documents: are they relevant enough?"""
    # TODO: Simple threshold on Qdrant score first
    # Later: LLM-as-judge for finer grading
    retrieved = state.get("retrieved", [])
    if not retrieved:
        return {"grade": "refuse"}

    # Simple threshold on the best cosine similarity
    max_score = max((r.get("score", 0) for r in retrieved), default=0)
    grade = "ok" if max_score >= GRADE_THRESHOLD else "refuse"
    return {"grade": grade}
