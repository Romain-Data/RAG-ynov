"""Unit tests for loaders and chunking (no Qdrant / FastEmbed)."""

from pathlib import Path

import pytest

from ingestion.chunking import chunk_documents
from ingestion.loaders import load_directory, load_file, load_markdown

# Fictitious FAQ used as a Markdown fixture only (never part of the corpus)
SAMPLES = Path(__file__).parent / "fixtures"
FAQ = SAMPLES / "admissions_faq.md"


class TestLoaders:
    def test_load_sample_faq_merges_manifest(self):
        """Sidecar manifest fields land in metadata; extra is flattened."""
        docs = load_markdown(FAQ)
        assert len(docs) == 4  # one per "## " section
        meta = docs[0]["metadata"]
        assert meta["section"] == "Comment s'inscrire avec un bac professionnel ?"
        assert meta["source"] == "admissions_faq.md"
        assert meta["doc_type"] == "faq"
        assert meta["year"] == 2026
        assert meta["language"] == "fr"
        assert meta["program"] is None
        assert meta["campus"] == "paris"
        assert "extra" not in meta
        assert docs[0]["prefix"] == (
            "Admissions Ynov 2026 — FAQ — Comment s'inscrire avec un bac professionnel ?\n"
        )

    def test_load_directory_finds_markdown(self):
        docs = load_directory(SAMPLES)
        assert len(docs) == 4
        assert all(d["metadata"]["doc_type"] == "faq" for d in docs)

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

    def test_markdown_without_sections_is_one_document(self, tmp_path: Path):
        md = tmp_path / "flat.md"
        md.write_text("# Titre\nUn seul bloc de texte.", encoding="utf-8")
        (tmp_path / "flat.manifest.yml").write_text("doc_type: faq\n", encoding="utf-8")
        docs = load_markdown(md)
        assert len(docs) == 1
        assert docs[0]["metadata"]["section"] is None

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
        # chunk_index restarts at 0 for each section document
        for section in {c["metadata"]["section"] for c in chunks}:
            indexes = [
                c["metadata"]["chunk_index"] for c in chunks if c["metadata"]["section"] == section
            ]
            assert indexes == list(range(len(indexes)))
        assert all(c["text"].startswith("Admissions Ynov 2026 — FAQ — ") for c in chunks)
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


def test_load_directory_skips_excluded_doc_types(tmp_path: Path):
    for name, doc_type in (("keep", "faq"), ("skip", "referentiel")):
        (tmp_path / f"{name}.md").write_text(f"# {name}\nbody", encoding="utf-8")
        (tmp_path / f"{name}.manifest.yml").write_text(f"doc_type: {doc_type}\n", encoding="utf-8")
    docs = load_directory(tmp_path, exclude_doc_types=["referentiel"])
    assert [d["metadata"]["doc_type"] for d in docs] == ["faq"]
    assert len(load_directory(tmp_path)) == 2
