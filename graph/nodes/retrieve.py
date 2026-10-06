import math

from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint, SparseVector

from app.core.config import settings
from graph.state import GraphState
from ingestion.embedder import embed_query, embed_sparse_query
from ingestion.indexer import DENSE, SPARSE, get_qdrant_client, vector_layout

# Tuned with eval/retrieval.py: 5 chunks with no cap often came from a single section
# (e.g. one RNCP equivalence table), crowding out the section that answered.
RETRIEVE_LIMIT = 10  # chunks passed to generation
CANDIDATE_LIMIT = 40  # chunks fetched from Qdrant before the per-section cap
MAX_PER_SECTION: int | None = 2  # max chunks from the same (source, section)
# Hybrid search (#14): the best BM25 chunks missing from the dense top take the last places.
# A rank fusion at equal weights lost q01 in the simulation (a tariff question drowned in
# lexical matches), so the dense order stays in charge and BM25 only adds SPARSE_INJECT chunks.
SPARSE_INJECT = 2
SPARSE_LIMIT = 10  # BM25 candidates looked at


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _hit(point: ScoredPoint, score: float) -> dict:
    payload = point.payload or {}
    return {
        "text": payload.get("text", ""),
        "score": score,
        "source": payload.get("source", ""),
        "page": payload.get("page"),
        "section": payload.get("section"),
        "section_text": payload.get("section_text"),
        "metadata": payload,
    }


def search(
    question: str,
    client: QdrantClient | None = None,
    limit: int = RETRIEVE_LIMIT,
    candidates: int = CANDIDATE_LIMIT,
    max_per_section: int | None = MAX_PER_SECTION,
    sparse_inject: int = SPARSE_INJECT,
) -> list[dict]:
    """Embed the question, fetch `candidates` nearest chunks, keep at most
    `max_per_section` per (source, section) and return the `limit` best.

    On a hybrid collection (dense + BM25), the last `sparse_inject` places go to the best
    BM25 chunks the dense search missed. `score` is always the dense cosine similarity,
    which the grading threshold is calibrated on."""
    client = client or get_qdrant_client()
    layout = vector_layout(client)
    query = embed_query(question)
    dense = client.query_points(
        collection_name=settings.qdrant_collection_name,
        query=query,
        using=None if layout == "legacy" else DENSE,
        limit=max(candidates, limit),
        with_payload=True,
    ).points

    sparse: list[ScoredPoint] = []
    inject = 0
    if layout == "hybrid" and sparse_inject > 0:
        sparse = client.query_points(
            collection_name=settings.qdrant_collection_name,
            query=SparseVector(**embed_sparse_query(question)),
            using=SPARSE,
            limit=SPARSE_LIMIT,
            with_payload=True,
            with_vectors=[DENSE],
        ).points
        inject = min(sparse_inject, limit)

    retrieved: list[dict] = []
    per_section: dict[tuple, int] = {}
    seen: set = set()

    def take(points: list[ScoredPoint], until: int, lexical: bool = False) -> None:
        for point in points:
            if len(retrieved) >= until:
                return
            payload = point.payload or {}
            key = (payload.get("source"), payload.get("section"))
            if point.id in seen:
                continue
            if max_per_section is not None and per_section.get(key, 0) >= max_per_section:
                continue
            seen.add(point.id)
            per_section[key] = per_section.get(key, 0) + 1
            score = point.score
            if lexical:  # the BM25 score means nothing to the threshold: use the cosine
                vectors = point.vector if isinstance(point.vector, dict) else {}
                vector = vectors.get(DENSE)
                score = (
                    _cosine(query, vector)
                    if isinstance(vector, list) and vector and isinstance(vector[0], float)
                    else 0.0
                )
            retrieved.append(_hit(point, score))

    take(dense, limit - inject)
    take(sparse, limit, lexical=True)
    take(dense, limit)
    return retrieved


def retrieve_node(state: GraphState) -> dict:
    """Embed question and search Qdrant for relevant chunks.

    A follow-up question is searched through its standalone rewrite, when there is one.
    """
    question = state.get("rewritten") or state.get("question", "")
    if not question:
        return {"retrieved": []}
    return {"retrieved": search(question)}
