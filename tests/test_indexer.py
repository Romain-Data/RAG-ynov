"""Indexer tests against an in-memory Qdrant (no server needed)."""

import pytest
from qdrant_client import QdrantClient

from app.core.config import settings
from ingestion.indexer import index_chunks, point_ids


def _chunk(source: str, section: str, index: int, text: str = "texte") -> dict:
    return {
        "text": text,
        "vector": [0.1] * 384,
        "metadata": {"source": source, "page": 1, "section": section, "chunk_index": index},
    }


@pytest.fixture
def client() -> QdrantClient:
    return QdrantClient(":memory:")


def _count(client: QdrantClient) -> int:
    return client.count(settings.qdrant_collection_name).count


class TestPointIds:
    def test_stable_across_runs(self):
        chunks = [_chunk("a.html", "Tarifs", 0), _chunk("a.html", "Tarifs", 1)]
        assert point_ids(chunks) == point_ids([dict(c) for c in chunks])

    def test_same_section_title_twice_in_a_source_gets_distinct_ids(self):
        chunks = [_chunk("a.html", "Voie d'accès", 0), _chunk("a.html", "Voie d'accès", 0)]
        assert len(set(point_ids(chunks))) == 2


class TestIndexChunks:
    def test_reingesting_does_not_duplicate(self, client: QdrantClient):
        chunks = [_chunk("a.html", "Tarifs", 0), _chunk("b.html", "Tarifs", 0)]
        index_chunks(chunks, client)
        index_chunks(chunks, client)
        assert _count(client) == 2

    def test_reingesting_updates_text(self, client: QdrantClient):
        index_chunks([_chunk("a.html", "Tarifs", 0, "9 000 €")], client)
        index_chunks([_chunk("a.html", "Tarifs", 0, "9 500 €")], client)
        points, _ = client.scroll(settings.qdrant_collection_name, with_payload=True)
        assert [p.payload["text"] for p in points] == ["9 500 €"]

    def test_chunks_that_left_the_corpus_are_deleted(self, client: QdrantClient):
        index_chunks([_chunk("a.html", "Tarifs", 0), _chunk("old.html", "Tarifs", 0)], client)
        index_chunks([_chunk("a.html", "Tarifs", 0)], client)
        points, _ = client.scroll(settings.qdrant_collection_name, with_payload=True)
        assert [p.payload["source"] for p in points] == ["a.html"]

    def test_empty_corpus_keeps_existing_points(self, client: QdrantClient):
        index_chunks([_chunk("a.html", "Tarifs", 0)], client)
        index_chunks([], client)
        assert _count(client) == 1

    def test_large_batch_is_split(self, client: QdrantClient):
        chunks = [_chunk("a.html", "Programme", i) for i in range(600)]
        assert index_chunks(chunks, client) == 600
        assert _count(client) == 600


def test_vectors_of_another_size_are_refused(client: QdrantClient):
    """Changing the embedding model must not silently mix vector sizes."""
    index_chunks([_chunk("a.html", "Tarifs", 0)], client)  # 384 dims
    bigger = _chunk("a.html", "Tarifs", 0)
    bigger["vector"] = [0.1] * 1024
    with pytest.raises(ValueError, match="embedding model changed"):
        index_chunks([bigger], client)


def test_a_collection_with_the_single_vector_schema_is_refused():
    """The collection of before the hybrid search must be replaced, not filled."""
    from qdrant_client.models import Distance, VectorParams

    from app.core.config import settings

    client = QdrantClient(":memory:")
    client.create_collection(
        settings.qdrant_collection_name, VectorParams(size=384, distance=Distance.COSINE)
    )
    with pytest.raises(ValueError, match="new collection"):
        index_chunks([_chunk("a.html", "Tarifs", 0)], client)


def test_sparse_vectors_are_stored_with_the_dense_ones(client: QdrantClient):
    from ingestion.indexer import vector_layout

    chunk = _chunk("a.html", "Tarifs", 0)
    chunk["sparse"] = {"indices": [1, 5], "values": [1.0, 2.0]}
    index_chunks([chunk], client)
    assert vector_layout(client) == "hybrid"
