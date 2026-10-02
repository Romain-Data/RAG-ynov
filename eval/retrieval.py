"""Retrieval evaluation: does the search return the chunks a question needs?

Indexes data/ into a local Qdrant (embedded mode, no server, .eval_qdrant/) with the
same loaders, chunking, embeddings and indexer as /api/ingest, then runs the questions
of eval/questions.yaml through graph.nodes.retrieve.search. The index is rebuilt only
when the chunks change (fingerprint of texts and metadata). No LLM call is made.

Usage:
    uv run python -m eval.retrieval [-v] [--limit 10 --candidates 40 --max-per-section 2]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import yaml

os.environ.setdefault("MAMMOUTH_API_KEY", "eval")  # Settings requires it; no LLM here

from qdrant_client import QdrantClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from graph.nodes import retrieve  # noqa: E402
from ingestion.chunking import CHUNK_SIZE, chunk_documents  # noqa: E402
from ingestion.embedder import embed_passages  # noqa: E402
from ingestion.indexer import index_chunks  # noqa: E402
from ingestion.loaders import load_directory  # noqa: E402

QUESTIONS = Path(__file__).with_name("questions.yaml")
INDEX_DIR = Path(".eval_qdrant")
FINGERPRINT = INDEX_DIR / "fingerprint"


def build_index(data_dir: Path, chunk_size: int = CHUNK_SIZE) -> QdrantClient:
    docs = load_directory(data_dir, settings.ingest_exclude_doc_type_list())
    chunks = chunk_documents(docs, chunk_size=chunk_size)
    digest = hashlib.sha256(
        json.dumps([(c["text"], c["metadata"]) for c in chunks], sort_keys=True,
                   default=str).encode()
    ).hexdigest()

    client = QdrantClient(path=str(INDEX_DIR))
    if FINGERPRINT.exists() and FINGERPRINT.read_text() == digest:
        print(f"Index à jour ({len(chunks)} chunks)")
        return client

    print(f"Indexation de {len(chunks)} chunks…", flush=True)
    if client.collection_exists(settings.qdrant_collection_name):
        client.delete_collection(settings.qdrant_collection_name)
    vectors = embed_passages([c["text"] for c in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk["vector"] = vector
    index_chunks(chunks, client)
    FINGERPRINT.write_text(digest)
    return client


def _matches(hit: dict, expect: dict) -> bool:
    return (hit["source"] == expect["source"]
            and expect["section"].lower() in (hit["section"] or "").lower())


def evaluate(client: QdrantClient, limit: int, candidates: int,
             max_per_section: int | None, verbose: bool) -> int:
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    passed = 0
    for q in questions:
        hits = retrieve.search(q["question"], client, limit=limit, candidates=candidates,
                               max_per_section=max_per_section)
        matched = [i for i, h in enumerate(hits) if any(_matches(h, e) for e in q["expect"])]
        distinct = {(hits[i]["source"], hits[i]["section"]) for i in matched}
        ok = len(distinct) >= q.get("min_distinct", 1)
        # The fact may also reach the LLM through another chunk (e.g. every chunk of a
        # formation carries "100 % en ligne" in its prefix): expect_text checks that.
        in_context = bool(q.get("expect_text")) and any(
            q["expect_text"].lower() in h["text"].lower() for h in hits
            if h["source"] in {e["source"] for e in q["expect"]}
        )
        ok = ok or in_context
        passed += ok
        rank = (f"rang {matched[0] + 1}" if matched
                else "fait présent dans le contexte" if in_context else "absent")
        print(f"{'✅' if ok else '❌'} {q['question'][:75]:75s} {rank}"
              + (f", {len(distinct)}/{q['min_distinct']} sections"
                 if q.get("min_distinct") else ""))
        if verbose or not ok:
            for i, h in enumerate(hits):
                mark = "→" if i in matched else " "
                print(f"     {mark} {h['score']:.3f} {h['source'][:45]:45s} | "
                      f"{(h['section'] or '')[:55]}")
    print(f"\n{passed}/{len(questions)} questions réussies "
          f"(limit={limit}, candidates={candidates}, max_per_section={max_per_section})")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--limit", type=int, default=retrieve.RETRIEVE_LIMIT)
    parser.add_argument("--candidates", type=int, default=retrieve.CANDIDATE_LIMIT)
    parser.add_argument("--max-per-section", type=int, default=retrieve.MAX_PER_SECTION)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("-v", "--verbose", action="store_true", help="show every result")
    args = parser.parse_args()
    client = build_index(args.data, args.chunk_size)
    evaluate(client, args.limit, args.candidates, args.max_per_section, args.verbose)


if __name__ == "__main__":
    main()
