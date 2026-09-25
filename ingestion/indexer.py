"""Qdrant indexer for upserting chunks."""
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client."""
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection(client: QdrantClient, vector_size: int = 384) -> None:
    """Create collection if it doesn't exist."""
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if settings.qdrant_collection_name not in names:
        client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def index_chunks(chunks: list[dict]) -> int:
    """
    Upsert chunks into Qdrant.

    Args:
        chunks: List of {text, metadata} with embeddings already computed

    Returns:
        Number of points upserted
    """
    client = get_qdrant_client()

    # Ensure collection exists (vector size from embedding model)
    # multilingual-e5-small = 384 dims
    ensure_collection(client, vector_size=384)

    points = []
    for chunk in chunks:
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=chunk["vector"],
            payload={
                "text": chunk["text"],
                **chunk["metadata"],
            },
        )
        points.append(point)

    client.upsert(collection_name=settings.qdrant_collection_name, points=points)
    return len(points)
