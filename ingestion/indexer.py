"""Qdrant indexer: syncs the collection with the chunks of the current corpus."""

import collections
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    FilterSelector,
    HasIdCondition,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.core.config import settings

# Fixed namespace so the same chunk gets the same point id on every ingestion.
POINT_ID_NAMESPACE = uuid.UUID("6f1c5e1a-3b9e-4d55-9a49-2f0d2b6f7c11")
UPSERT_BATCH_SIZE = 256
# Named vectors of a point: the dense embedding and the BM25 sparse vector (lot 4 of #14).
DENSE = "dense"
SPARSE = "bm25"


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client."""
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection(client: QdrantClient, vector_size: int = 384) -> None:
    """Create the collection if it doesn't exist; refuse another schema or vector size."""
    collections_ = client.get_collections().collections
    names = [c.name for c in collections_]

    if settings.qdrant_collection_name in names:
        params = client.get_collection(settings.qdrant_collection_name).config.params
        vectors = params.vectors
        if not isinstance(vectors, dict) or DENSE not in vectors:
            raise ValueError(
                f"Collection {settings.qdrant_collection_name!r} has the single-vector schema "
                "of before the hybrid search. Ingest into a new collection "
                "(QDRANT_COLLECTION_NAME), then switch the variable."
            )
        existing = vectors[DENSE].size
        if existing != vector_size:
            raise ValueError(
                f"Collection {settings.qdrant_collection_name!r} holds {existing}-dim vectors "
                f"but the embedding model produces {vector_size}: the embedding model changed. "
                "Delete the collection, then re-ingest."
            )
    else:
        client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config={DENSE: VectorParams(size=vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={SPARSE: SparseVectorParams(modifier=Modifier.IDF)},
        )


def vector_layout(client: QdrantClient) -> str:
    """ "hybrid" (dense + BM25), "dense" (named dense only) or "legacy" (one unnamed vector,
    the collection of before the hybrid search: still searchable, until it is replaced)."""
    params = client.get_collection(settings.qdrant_collection_name).config.params
    if not isinstance(params.vectors, dict):
        return "legacy"
    return "hybrid" if SPARSE in (params.sparse_vectors or {}) else "dense"


def point_ids(chunks: list[dict]) -> list[str]:
    """Deterministic point id per chunk: uuid5 of (source, section, chunk_index).

    A source can hold two sections with the same title, so repeated keys get an
    occurrence number; ids stay stable as long as the corpus is loaded in the same order.
    """
    seen: collections.Counter[tuple] = collections.Counter()
    ids = []
    for chunk in chunks:
        meta = chunk["metadata"]
        key = (meta.get("source"), meta.get("page"), meta.get("section"), meta.get("chunk_index"))
        occurrence = seen[key]
        seen[key] += 1
        ids.append(str(uuid.uuid5(POINT_ID_NAMESPACE, repr((*key, occurrence)))))
    return ids


def _vectors(chunk: dict) -> dict:
    vectors: dict = {DENSE: chunk["vector"]}
    if chunk.get("sparse"):
        vectors[SPARSE] = SparseVector(**chunk["sparse"])
    return vectors


def index_chunks(chunks: list[dict], client: QdrantClient | None = None) -> int:
    """
    Sync the collection with `chunks`: upsert them, then delete every other point.

    Re-ingesting replaces points instead of duplicating them, and chunks that left the
    corpus (removed file, shorter section) are cleaned up. Deletion runs after the
    upsert, so the collection is never empty during a re-ingestion.

    Args:
        chunks: List of {text, metadata, vector, sparse} with embeddings already computed
        client: Qdrant client (defaults to the configured server)

    Returns:
        Number of points upserted
    """
    client = client or get_qdrant_client()

    # Ensure collection exists, sized for the embedding model in use
    if chunks:
        ensure_collection(client, vector_size=len(chunks[0]["vector"]))

    ids = point_ids(chunks)
    points = [
        PointStruct(
            id=point_id,
            vector=_vectors(chunk),
            payload={"text": chunk["text"], **chunk["metadata"]},
        )
        for point_id, chunk in zip(ids, chunks, strict=True)
    ]
    for start in range(0, len(points), UPSERT_BATCH_SIZE):
        client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=points[start : start + UPSERT_BATCH_SIZE],
        )

    if ids:  # never wipe the collection on an empty corpus
        client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=FilterSelector(
                filter=Filter(must_not=[HasIdCondition(has_id=ids)])  # type: ignore[arg-type]
            ),
        )
    return len(points)
