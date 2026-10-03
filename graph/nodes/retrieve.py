from qdrant_client import QdrantClient

from app.core.config import settings
from graph.state import GraphState
from ingestion.embedder import embed_query
from ingestion.indexer import get_qdrant_client

# Tuned with eval/retrieval.py: 5 chunks with no cap often came from a single section
# (e.g. one RNCP equivalence table), crowding out the section that answered.
RETRIEVE_LIMIT = 10  # chunks passed to generation
CANDIDATE_LIMIT = 40  # chunks fetched from Qdrant before the per-section cap
MAX_PER_SECTION: int | None = 2  # max chunks from the same (source, section)


def search(
    question: str,
    client: QdrantClient | None = None,
    limit: int = RETRIEVE_LIMIT,
    candidates: int = CANDIDATE_LIMIT,
    max_per_section: int | None = MAX_PER_SECTION,
) -> list[dict]:
    """Embed the question, fetch `candidates` nearest chunks, keep at most
    `max_per_section` per (source, section) and return the `limit` best."""
    client = client or get_qdrant_client()
    response = client.query_points(
        collection_name=settings.qdrant_collection_name,
        query=embed_query(question),
        limit=max(candidates, limit),
        with_payload=True,
    )

    retrieved: list[dict] = []
    per_section: dict[tuple, int] = {}
    for point in response.points:
        payload = point.payload or {}
        key = (payload.get("source"), payload.get("section"))
        if max_per_section is not None and per_section.get(key, 0) >= max_per_section:
            continue
        per_section[key] = per_section.get(key, 0) + 1
        retrieved.append({
            "text": payload.get("text", ""),
            "score": point.score,
            "source": payload.get("source", ""),
            "page": payload.get("page"),
            "section": payload.get("section"),
            "metadata": payload,
        })
        if len(retrieved) == limit:
            break
    return retrieved


def retrieve_node(state: GraphState) -> dict:
    """Embed question and search Qdrant for relevant chunks.

    A follow-up question is searched through its standalone rewrite, when there is one.
    """
    question = state.get("rewritten") or state.get("question", "")
    if not question:
        return {"retrieved": []}
    return {"retrieved": search(question)}
