"""Retrieval tests against an in-memory Qdrant, with a stubbed query embedding."""

import pytest
from qdrant_client import QdrantClient

from graph.nodes import retrieve
from ingestion.indexer import index_chunks


def _chunk(section: str, index: int, vector: list[float]) -> dict:
    return {
        "text": f"{section} {index}",
        "vector": vector,
        "metadata": {"source": "a.html", "page": 1, "section": section, "chunk_index": index},
    }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> QdrantClient:
    query = [1.0] + [0.0] * 383
    monkeypatch.setattr(retrieve, "embed_query", lambda _q: query)
    client = QdrantClient(":memory:")
    near = [1.0, 0.1] + [0.0] * 382  # very close to the query
    far = [1.0, 0.5] + [0.0] * 382  # less close
    chunks = [_chunk("Programme", i, near) for i in range(5)] + [_chunk("Tarifs", 0, far)]
    index_chunks(chunks, client)
    return client


def test_per_section_cap_makes_room_for_other_sections(client: QdrantClient):
    hits = retrieve.search("q", client, limit=3, candidates=10, max_per_section=2)
    assert [h["section"] for h in hits] == ["Programme", "Programme", "Tarifs"]


def test_without_cap_one_section_can_fill_the_results(client: QdrantClient):
    hits = retrieve.search("q", client, limit=3, candidates=10, max_per_section=None)
    assert {h["section"] for h in hits} == {"Programme"}


def test_retrieve_node_uses_defaults(client: QdrantClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(retrieve, "get_qdrant_client", lambda: client)
    retrieved = retrieve.retrieve_node({"question": "q"})["retrieved"]  # type: ignore[typeddict-item]
    assert len(retrieved) == 3  # 2 Programme (cap) + 1 Tarifs


def _sparse(*terms: int) -> dict:
    return {"indices": list(terms), "values": [1.0] * len(terms)}


@pytest.fixture
def hybrid_client(monkeypatch: pytest.MonkeyPatch) -> QdrantClient:
    """12 sections close to the query in the dense space, one far away that holds the term."""
    monkeypatch.setattr(retrieve, "embed_query", lambda _q: [1.0] + [0.0] * 383)
    monkeypatch.setattr(retrieve, "embed_sparse_query", lambda _q: _sparse(42))
    client = QdrantClient(":memory:")
    chunks = [
        {**_chunk(f"Section {i}", 0, [1.0, 0.01 * i] + [0.0] * 382), "sparse": _sparse(7)}
        for i in range(12)
    ]
    chunks.append({**_chunk("Parcoursup", 0, [0.2, 1.0] + [0.0] * 382), "sparse": _sparse(42)})
    index_chunks(chunks, client)
    return client


def test_the_best_bm25_chunk_missing_from_the_dense_top_takes_a_place(hybrid_client):
    hits = retrieve.search("q", hybrid_client, limit=10, candidates=10, sparse_inject=2)
    assert len(hits) == 10
    assert "Parcoursup" in [h["section"] for h in hits]
    assert [h["section"] for h in hits[:8]] == [f"Section {i}" for i in range(8)]


def test_without_injection_the_dense_order_decides(hybrid_client):
    hits = retrieve.search("q", hybrid_client, limit=10, candidates=10, sparse_inject=0)
    assert "Parcoursup" not in [h["section"] for h in hits]


def test_a_bm25_hit_keeps_its_cosine_score_for_the_threshold(hybrid_client):
    hits = retrieve.search("q", hybrid_client, limit=10, candidates=10, sparse_inject=2)
    parcoursup = next(h for h in hits if h["section"] == "Parcoursup")
    expected = 0.2 / (0.2**2 + 1.0**2) ** 0.5
    assert parcoursup["score"] == pytest.approx(expected, abs=1e-4)


def test_a_chunk_found_by_both_searches_is_returned_once(hybrid_client):
    hits = retrieve.search("q", hybrid_client, limit=13, candidates=13, sparse_inject=2)
    sections = [h["section"] for h in hits]
    assert len(sections) == len(set(sections)) == 13


def test_a_collection_of_before_the_hybrid_search_is_still_searchable(
    monkeypatch: pytest.MonkeyPatch,
):
    from qdrant_client.models import Distance, PointStruct, VectorParams

    from app.core.config import settings

    monkeypatch.setattr(retrieve, "embed_query", lambda _q: [1.0, 0.0])
    client = QdrantClient(":memory:")
    client.create_collection(
        settings.qdrant_collection_name, VectorParams(size=2, distance=Distance.COSINE)
    )
    client.upsert(
        settings.qdrant_collection_name,
        [PointStruct(id=1, vector=[1.0, 0.1], payload={"text": "t", "section": "S"})],
    )
    hits = retrieve.search("q", client)
    assert [h["section"] for h in hits] == ["S"]
