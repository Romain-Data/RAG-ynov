"""Retrieval evaluation: does the search return the chunks a question needs?

Indexes data/ into a local Qdrant (embedded mode, no server, .eval_qdrant/) with the
same loaders, chunking, embeddings and indexer as /api/ingest, then runs the questions
of eval/questions.yaml through graph.nodes.retrieve.search. The index is rebuilt only
when the chunks change (fingerprint of texts and metadata). No LLM call is made.

A question also gets flagged when its best score is below the grading threshold: the
API would refuse it without calling the LLM, even if the right chunk is retrieved.

Usage:
    uv run python -m eval.retrieval [-v] [--limit 10 --candidates 40 --max-per-section 2]
    uv run python -m eval.retrieval --save "label"   # writes eval/results/<run_id>.json
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MAMMOUTH_API_KEY", "eval")  # Settings requires it; no LLM here

from qdrant_client import QdrantClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from eval.results import (  # noqa: E402
    QUESTION_SET,
    git_commit,
    load_questions,
    next_run_id,
    save_run,
)
from graph.nodes import retrieve  # noqa: E402
from graph.nodes.grade import GRADE_THRESHOLD  # noqa: E402
from ingestion.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_documents  # noqa: E402
from ingestion.embedder import embed_passages  # noqa: E402
from ingestion.indexer import index_chunks  # noqa: E402
from ingestion.loaders import load_directory  # noqa: E402

INDEX_DIR = Path(".eval_qdrant")
FINGERPRINT = INDEX_DIR / "fingerprint"


def build_index(data_dir: Path, chunk_size: int = CHUNK_SIZE) -> tuple[QdrantClient, int]:
    docs = load_directory(data_dir, settings.ingest_exclude_doc_type_list())
    chunks = chunk_documents(docs, chunk_size=chunk_size)
    digest = hashlib.sha256(
        json.dumps([(c["text"], c["metadata"]) for c in chunks], sort_keys=True,
                   default=str).encode()
    ).hexdigest()

    client = QdrantClient(path=str(INDEX_DIR))
    if FINGERPRINT.exists() and FINGERPRINT.read_text() == digest:
        print(f"Index à jour ({len(chunks)} chunks)")
        return client, len(chunks)

    print(f"Indexation de {len(chunks)} chunks…", flush=True)
    if client.collection_exists(settings.qdrant_collection_name):
        client.delete_collection(settings.qdrant_collection_name)
    vectors = embed_passages([c["text"] for c in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk["vector"] = vector
    index_chunks(chunks, client)
    FINGERPRINT.write_text(digest)
    return client, len(chunks)


def _matches(hit: dict, expect: dict) -> bool:
    return (hit["source"] == expect["source"]
            and expect["section"].lower() in (hit["section"] or "").lower())


def evaluate(client: QdrantClient, limit: int, candidates: int,
             max_per_section: int | None, verbose: bool) -> list[dict]:
    results = []
    for q in load_questions():
        if q.get("out_of_scope") == "llm":
            continue  # passes the threshold by design; only the LLM can decline it
        hits = retrieve.search(q["question"], client, limit=limit, candidates=candidates,
                               max_per_section=max_per_section)
        matched = [i for i, h in enumerate(hits)
                   if any(_matches(h, e) for e in q.get("expect", []))]
        distinct = {(hits[i]["source"], hits[i]["section"]) for i in matched}
        ok = len(distinct) >= q.get("min_distinct", 1)
        # The fact may also reach the LLM through another chunk (e.g. every chunk of a
        # formation carries "100 % en ligne" in its prefix): expect_text checks that.
        in_context = bool(q.get("expect_text")) and any(
            q["expect_text"].lower() in h["text"].lower() for h in hits
            if h["source"] in {e["source"] for e in q.get("expect", [])}
        )
        ok = ok or in_context
        top_score = max((h["score"] for h in hits), default=0.0)
        refused = top_score < GRADE_THRESHOLD
        if q.get("out_of_scope"):
            ok = refused  # an out-of-scope question passes when the threshold refuses it
        results.append({
            "question_id": q["id"],
            "question": q["question"],
            "out_of_scope": q.get("out_of_scope"),
            "passed": ok,
            "rank": matched[0] + 1 if matched else None,
            "in_context": in_context,
            "distinct_sections": len(distinct),
            "min_distinct": q.get("min_distinct", 1),
            "top_score": round(top_score, 3),
            "refused_by_threshold": refused,
            "retrieved": [{"source": h["source"], "section": h["section"],
                           "score": round(h["score"], 3)} for h in hits],
        })

        rank = ("hors périmètre" if q.get("out_of_scope")
                else f"rang {matched[0] + 1}" if matched
                else "fait présent dans le contexte" if in_context else "absent")
        print(f"{'✅' if ok else '❌'} {q['id']} {q['question'][:70]:70s} {rank}"
              + (f", {len(distinct)}/{q['min_distinct']} sections"
                 if q.get("min_distinct") else "")
              + (f"  ⛔ refusée (score {top_score:.3f} < {GRADE_THRESHOLD})" if refused
                 else f"  (score {top_score:.3f})" if q.get("out_of_scope") else ""))
        if verbose or not ok:
            for i, h in enumerate(hits):
                mark = "→" if i in matched else " "
                print(f"     {mark} {h['score']:.3f} {h['source'][:45]:45s} | "
                      f"{(h['section'] or '')[:55]}")
    in_scope = [r for r in results if not r["out_of_scope"]]
    out_scope = [r for r in results if r["out_of_scope"]]
    print(f"\nDans le périmètre : {sum(r['passed'] for r in in_scope)}/{len(in_scope)} réussies, "
          f"{sum(r['refused_by_threshold'] for r in in_scope)} refusée(s) à tort par le seuil")
    if out_scope:
        print(f"Hors périmètre : {sum(r['passed'] for r in out_scope)}/{len(out_scope)} "
              f"refusées par le seuil")
    print(f"(limit={limit}, candidates={candidates}, max_per_section={max_per_section}, "
          f"seuil={GRADE_THRESHOLD})")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--limit", type=int, default=retrieve.RETRIEVE_LIMIT)
    parser.add_argument("--candidates", type=int, default=retrieve.CANDIDATE_LIMIT)
    parser.add_argument("--max-per-section", type=int, default=retrieve.MAX_PER_SECTION)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--save", metavar="LABEL", help="save the run in eval/results/")
    parser.add_argument("--notes", default="", help="free text saved with the run")
    parser.add_argument("-v", "--verbose", action="store_true", help="show every result")
    args = parser.parse_args()
    client, n_chunks = build_index(args.data, args.chunk_size)
    results = evaluate(client, args.limit, args.candidates, args.max_per_section,
                       args.verbose)

    if args.save:
        date = dt.date.today().isoformat()
        path = save_run({
            "run_id": next_run_id(date, args.save),
            "date": date,
            "kind": "retrieval",
            "environment": "local",
            "git_commit": git_commit(),
            "question_set": QUESTION_SET,
            "milestone": False,
            "label": args.save,
            "notes": args.notes,
            "config": {
                "embedding_model": settings.embedding_model,
                "chunk_size": args.chunk_size,
                "chunk_overlap": CHUNK_OVERLAP,
                "n_chunks": n_chunks,
                "limit": args.limit,
                "candidates": args.candidates,
                "max_per_section": args.max_per_section,
                "grade_threshold": GRADE_THRESHOLD,
            },
            "results": results,
        })
        print(f"Résultats enregistrés : {path}")


if __name__ == "__main__":
    main()
