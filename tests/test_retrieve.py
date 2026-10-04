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
