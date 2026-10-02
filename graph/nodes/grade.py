from graph.state import GraphState

# Minimum top cosine score to answer; below it the question is refused without calling
# the LLM. Also used by eval/ to flag questions that would be refused.
# Calibrated on the eval set (2026-10-02, chunks of 300, MiniLM): in-scope questions
# score 0.497-0.887, unrelated ones at most 0.437. 0.5 refused q13 (EC-02); 0.45 sits
# closer to the unrelated ones, since refusing a valid question costs more than letting
# the LLM decline an off-topic one. Questions on other schools score 0.59-0.61 and
# cannot be filtered here (EC-12): the prompt handles them. Recalibrate with
# eval/retrieval.py when chunking or the embedding model change.
GRADE_THRESHOLD = 0.45


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
