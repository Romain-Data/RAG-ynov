"""Embedder tests with a fake model: prefixes and per-model instances."""
import pytest

from app.core.config import settings
from ingestion import embedder


class FakeModel:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def embed(self, texts):
        self.seen += texts
        return [[float(len(t))] for t in texts]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    model = FakeModel()
    monkeypatch.setattr(embedder, "get_embedding_model", lambda: model)
    return model


def test_e5_gets_query_and_passage_prefixes(fake: FakeModel, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "embedding_model", "intfloat/multilingual-e5-large")
    embedder.embed_query("prix ?")
    embedder.embed_passages(["9 000 €"])
    assert fake.seen == ["query: prix ?", "passage: 9 000 €"]


def test_paraphrase_models_get_no_prefix(fake: FakeModel, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "embedding_model",
                        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    embedder.embed_query("prix ?")
    assert fake.seen == ["prix ?"]


def test_snapshot_without_symlinks(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """The HF cache symlinks files to ../../blobs/; the materialized copy must not."""
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / "abc").write_text("weights")
    snapshot = tmp_path / "models--org--model" / "snapshots" / "rev1"
    snapshot.mkdir(parents=True)
    (snapshot / "model.onnx_data").symlink_to("../../../blobs/abc")
    monkeypatch.setattr(embedder.TextEmbedding, "list_supported_models",
                        lambda: [{"model": "org/model", "sources": {"hf": "org/model"}}])

    path = embedder._snapshot_without_symlinks("org/model", str(tmp_path))

    assert path == tmp_path / "materialized" / "org--model" / "rev1"
    data = path / "model.onnx_data"
    assert not data.is_symlink() and data.read_text() == "weights"
