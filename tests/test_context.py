"""The context sent to the LLM: whole short sections, one source per section (EC-17)."""

from graph.nodes import generate
from graph.nodes.generate import build_context
from ingestion.chunking import SECTION_CONTEXT_MAX, chunk_documents


def _hit(text: str, section: str, score: float, section_text: str | None = None) -> dict:
    return {
        "text": text,
        "source": "a.html",
        "page": 1,
        "section": section,
        "score": score,
        "section_text": section_text,
    }


def test_a_short_section_is_sent_whole_once() -> None:
    whole = "Prefix\nline one. line two. line three."
    hits = [_hit("line one.", "S", 0.8, whole), _hit("line three.", "S", 0.6, whole)]
    context, sources = build_context(hits)
    assert context == f"[Source 1: a.html, p.1]\n{whole}"
    assert sources == [{"source": "a.html", "page": 1, "section": "S", "score": 0.8}]


def test_without_section_text_the_retrieved_chunks_are_joined() -> None:
    """An index built before section_text, or a long section."""
    context, sources = build_context([_hit("one", "S", 0.8), _hit("two", "S", 0.7)])
    assert context.endswith("one\ntwo") and len(sources) == 1


def test_sources_follow_the_order_of_the_best_chunks() -> None:
    hits = [_hit("a", "S1", 0.9), _hit("b", "S2", 0.8), _hit("c", "S1", 0.7)]
    _, sources = build_context(hits)
    assert [s["section"] for s in sources] == ["S1", "S2"]


def test_the_context_budget_drops_the_last_sections(monkeypatch) -> None:
    monkeypatch.setattr(generate, "MAX_CONTEXT_CHARS", 30)
    hits = [_hit("x" * 20, "S1", 0.9), _hit("y" * 20, "S2", 0.8)]
    _, sources = build_context(hits)
    assert [s["section"] for s in sources] == ["S1"]


def test_chunks_of_a_short_section_carry_the_whole_section() -> None:
    doc = {"text": "Phrase une. " * 40, "metadata": {"section": "S"}, "prefix": "P\n"}
    chunks = chunk_documents([doc])
    assert len(chunks) > 1
    assert all(c["metadata"]["section_text"] == "P\n" + doc["text"] for c in chunks)


def test_a_long_section_or_a_single_chunk_has_no_section_text() -> None:
    long_doc = {"text": "Phrase une. " * (SECTION_CONTEXT_MAX // 5), "metadata": {}}
    short_doc = {"text": "Court.", "metadata": {}}
    assert all("section_text" not in c["metadata"] for c in chunk_documents([long_doc, short_doc]))
