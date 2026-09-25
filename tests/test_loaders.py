"""Unit tests for loaders and chunking (no Qdrant / FastEmbed)."""
from pathlib import Path

import pytest

from ingestion.chunking import chunk_documents
from ingestion.loaders import load_directory, load_file, load_markdown

SAMPLES = Path("data/samples")
FAQ = SAMPLES / "admissions_faq.md"


class TestLoaders:
    def test_load_sample_faq_merges_manifest(self):
        """Sidecar manifest fields land in metadata; extra is flattened."""
        docs = load_markdown(FAQ)
        assert len(docs) == 1
        meta = docs[0]["metadata"]
        assert meta["source"] == "admissions_faq.md"
        assert meta["doc_type"] == "faq"
        assert meta["year"] == 2026
        assert meta["language"] == "fr"
        assert meta["program"] is None
        assert meta["campus"] == "paris"
        assert "extra" not in meta
        assert "Comment s'inscrire" in docs[0]["text"]

    def test_load_directory_finds_markdown(self):
        docs = load_directory(SAMPLES)
        assert len(docs) == 1
        assert docs[0]["metadata"]["doc_type"] == "faq"

    def test_missing_manifest_raises(self, tmp_path: Path):
        orphan = tmp_path / "orphan.md"
        orphan.write_text("# Hello\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Manifest not found"):
            load_file(orphan)

    def test_unsupported_extension_raises(self, tmp_path: Path):
        txt = tmp_path / "notes.txt"
        txt.write_text("nope", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_file(txt)

    def test_manifest_wins_over_loader_source(self, tmp_path: Path):
        """If the sidecar sets source, it overrides path.name (M4)."""
        md = tmp_path / "file.md"
        md.write_text("# Title\nbody", encoding="utf-8")
        (tmp_path / "file.manifest.yml").write_text(
            "source: canonical.md\ndoc_type: faq\nprogram: null\nyear: 2026\n"
            "title: T\nlanguage: fr\nextra:\n  campus: lyon\n",
            encoding="utf-8",
        )
        docs = load_markdown(md)
        assert docs[0]["metadata"]["source"] == "canonical.md"
        assert docs[0]["metadata"]["campus"] == "lyon"


class TestChunking:
    def test_faq_splits_into_multiple_chunks(self):
        docs = load_markdown(FAQ)
        chunks = chunk_documents(docs, chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 2
        indexes = [c["metadata"]["chunk_index"] for c in chunks]
        assert indexes == list(range(len(chunks)))
        # Manifest fields survive the split
        assert all(c["metadata"]["doc_type"] == "faq" for c in chunks)
        assert all(c["metadata"]["campus"] == "paris" for c in chunks)

    def test_empty_text_yields_no_chunks(self):
        chunks = chunk_documents(
            [{"text": "   \n", "metadata": {"source": "x"}}],
            chunk_size=500,
            chunk_overlap=50,
        )
        assert chunks == []
