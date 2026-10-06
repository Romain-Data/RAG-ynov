"""The ingestion command: dense and BM25 vectors reach the index."""

from pathlib import Path

from ingestion import run


def test_chunks_get_both_vectors_and_are_indexed(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "a.md").write_text("# Titre\n\n## Section\nUn texte court.", encoding="utf-8")
    (tmp_path / "a.manifest.yml").write_text("source: a.md\ndoc_type: info\n", encoding="utf-8")
    seen: list[dict] = []
    monkeypatch.setattr(run, "embed_passages", lambda texts: [[0.1] * 384 for _ in texts])
    monkeypatch.setattr(
        run, "embed_sparse_passages", lambda texts: [{"indices": [1], "values": [1.0]}] * len(texts)
    )
    monkeypatch.setattr(run, "index_chunks", lambda chunks: seen.extend(chunks) or len(chunks))
    messages: list[str] = []
    assert run.ingest_directory(tmp_path, messages.append) == 1
    assert seen[0]["vector"] == [0.1] * 384 and seen[0]["sparse"]["indices"] == [1]
    assert any("1 points" in m for m in messages)


def test_an_empty_folder_indexes_nothing(tmp_path: Path) -> None:
    assert run.ingest_directory(tmp_path) == 0


def test_the_collection_option_overrides_the_configured_one(monkeypatch, capsys) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "qdrant_collection_name", "ynov_rag")
    monkeypatch.setattr(run, "ingest_directory", lambda _data, _log: 0)
    monkeypatch.setattr("sys.argv", ["run", "--collection", "ynov_rag_v2"])
    run.main()
    assert settings.qdrant_collection_name == "ynov_rag_v2"
    assert "Collection : ynov_rag_v2" in capsys.readouterr().out
