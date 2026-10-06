"""Retrieval evaluation: does the search return the chunks a question needs?

Indexes data/ into a local Qdrant (embedded mode, no server, .eval_qdrant/) with the
same loaders, chunking, embeddings and indexer as /api/ingest, then runs the questions
of eval/questions.yaml through graph.nodes.retrieve.search. The index is rebuilt only
when the chunks change (fingerprint of texts and metadata). No LLM call is made.

A question also gets flagged when its best score is below the grading threshold: the
API would refuse it without calling the LLM, even if the right chunk is retrieved.

To compare embedding models, --embedding-model overrides the configured one (each
model and chunk size gets its own index under .eval_qdrant/), and --threshold the
grading threshold, which must be recalibrated per model: the run prints the score gap
between the weakest in-scope question and the strongest out-of-scope one.

Embeddings are computed in batches and checkpointed: with --max-minutes, a run stops
cleanly when its time budget is spent (exit code 3) and the next run resumes. Large
models (e5-large: ~35 min for the corpus on a laptop CPU) need several runs.

Usage:
    uv run python -m eval.retrieval [-v] [--limit 10 --candidates 40 --max-per-section 2]
    uv run python -m eval.retrieval --save "label"   # writes eval/results/<run_id>.json
    uv run python -m eval.retrieval --embedding-model intfloat/multilingual-e5-large \
        --chunk-size 500 --threshold 0.8 --save "e5-large-500"
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

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
from graph.nodes.generate import build_context  # noqa: E402
from graph.nodes.grade import GRADE_THRESHOLD  # noqa: E402
from ingestion.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_documents  # noqa: E402
from ingestion.embedder import (  # noqa: E402
    SPARSE_LANGUAGE,
    SPARSE_MODEL,
    embed_passages,
    embed_sparse_passages,
    get_embedding_model,
)
from ingestion.indexer import index_chunks  # noqa: E402
from ingestion.loaders import load_directory  # noqa: E402

INDEX_ROOT = Path(".eval_qdrant")
EMBED_BATCH = 256
BUDGET_EXHAUSTED = 3  # exit code: index not finished, run again to resume


def embed_with_checkpoint(
    texts: list[str], directory: Path, digest: str, max_minutes: float | None
) -> tuple[list[list[float]], float] | None:
    """Embed `texts` in batches, saving progress in `directory`.

    Returns (vectors, seconds spent in this run and previous ones), or None when the time
    budget ran out before the end (progress is kept for the next run).
    """
    checkpoint = directory / "embeddings.partial.json"
    state: dict[str, Any] = {"digest": digest, "vectors": [], "seconds": 0.0}
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text())
        if saved.get("digest") == digest:
            state = saved
            print(
                f"Reprise : {len(state['vectors'])}/{len(texts)} embeddings déjà calculés",
                flush=True,
            )
    start = time.time()
    while len(state["vectors"]) < len(texts):
        if max_minutes is not None and time.time() - start > max_minutes * 60:
            checkpoint.write_text(json.dumps(state))
            return None
        done = len(state["vectors"])
        batch_start = time.time()
        state["vectors"] += embed_passages(texts[done : done + EMBED_BATCH])
        state["seconds"] += time.time() - batch_start
        checkpoint.write_text(json.dumps(state))
        print(
            f"  embeddings {len(state['vectors'])}/{len(texts)} ({state['seconds'] / 60:.1f} min)",
            flush=True,
        )
    checkpoint.unlink()
    return state["vectors"], state["seconds"]


def index_dir(model: str, chunk_size: int, data_dir: Path = Path("data")) -> Path:
    """One index per model, chunk size and data folder: the CI corpus must not overwrite the
    index of the full corpus."""
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    suffix = "" if data_dir == Path("data") else f"-{data_dir.name}"
    return INDEX_ROOT / f"{slug}-{chunk_size}{suffix}"


def context_facts(question: dict, hits: list[dict]) -> dict:
    """Which expected facts (`context_must`, else `answer_must`) are in the text the LLM gets.

    The "right section retrieved" criterion misses a chunk that is in the section but does
    not hold the fact (q07, q10, q11): this one reads the context the way the LLM does.
    """
    patterns = question.get("context_must") or question.get("answer_must") or []
    context = re.sub(r"[\s\u00a0\u202f]+", " ", build_context(hits)[0])
    found = [bool(re.search(p, context, re.IGNORECASE)) for p in patterns]
    return {
        "facts_in_context": f"{sum(found)}/{len(found)}",
        "context_ok": bool(found) and all(found),
        "context_chars": len(context),
    }


def truncation_stats(chunks: list[dict]) -> dict:
    """Share of chunks longer than the model's token window (cut before embedding)."""
    try:
        tokenizer = get_embedding_model().model.tokenizer  # type: ignore[attr-defined]
        max_length = tokenizer.truncation["max_length"]
        tokenizer.no_truncation()
        lengths = [len(tokenizer.encode(c["text"]).ids) for c in chunks]
        tokenizer.enable_truncation(max_length)
    except (AttributeError, KeyError, TypeError):
        return {}
    return {
        "max_tokens": max_length,
        "median_tokens": int(statistics.median(lengths)),
        "truncated_share": round(sum(n > max_length for n in lengths) / len(lengths), 3),
    }


def build_index(
    data_dir: Path, chunk_size: int = CHUNK_SIZE, max_minutes: float | None = None
) -> tuple[QdrantClient, dict]:
    """Index data/ with the configured embedding model (cached per model and chunk size).

    Returns (client, info) with n_chunks, build_seconds (None when cached) and the
    token truncation stats of the model.
    """
    docs = load_directory(data_dir, settings.ingest_exclude_doc_type_list())
    chunks = chunk_documents(docs, chunk_size=chunk_size)
    digest = hashlib.sha256(
        json.dumps(
            [settings.embedding_model, SPARSE_MODEL, SPARSE_LANGUAGE]
            + [(c["text"], c["metadata"]) for c in chunks],
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    directory = index_dir(settings.embedding_model, chunk_size, data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    fingerprint = directory / "fingerprint"
    info_file = directory / "info.json"

    client = QdrantClient(path=str(directory))
    if fingerprint.exists() and fingerprint.read_text() == digest and info_file.exists():
        info = json.loads(info_file.read_text())
        print(f"Index à jour ({info['n_chunks']} chunks, {settings.embedding_model})")
        return client, {**info, "build_seconds": None}

    print(f"Indexation de {len(chunks)} chunks avec {settings.embedding_model}…", flush=True)
    embedded = embed_with_checkpoint([c["text"] for c in chunks], directory, digest, max_minutes)
    if embedded is None:
        print(
            f"Budget de {max_minutes} min écoulé : relancer la même commande pour "
            "reprendre l'indexation.",
            flush=True,
        )
        sys.exit(BUDGET_EXHAUSTED)
    vectors, embed_seconds = embedded
    if client.collection_exists(settings.qdrant_collection_name):
        client.delete_collection(settings.qdrant_collection_name)
    sparse = embed_sparse_passages([c["text"] for c in chunks])
    for chunk, vector, bm25 in zip(chunks, vectors, sparse, strict=True):
        chunk["vector"] = vector
        chunk["sparse"] = bm25
    index_chunks(chunks, client)
    info = {
        "n_chunks": len(chunks),
        "embed_seconds": round(embed_seconds, 1),
        **truncation_stats(chunks),
    }
    info_file.write_text(json.dumps(info))
    fingerprint.write_text(digest)
    print(f"Embeddings calculés en {embed_seconds:.0f} s", flush=True)
    return client, {**info, "build_seconds": round(embed_seconds, 1)}


def _matches(hit: dict, expect: dict) -> bool:
    return (
        hit["source"] == expect["source"]
        and expect["section"].lower() in (hit["section"] or "").lower()
    )


def evaluate(
    client: QdrantClient,
    limit: int,
    candidates: int,
    max_per_section: int | None,
    verbose: bool,
    threshold: float = GRADE_THRESHOLD,
) -> list[dict]:
    results = []
    for q in load_questions():
        if q.get("out_of_scope") == "llm":
            continue  # passes the threshold by design; only the LLM can decline it
        start = time.time()
        hits = retrieve.search(
            q["question"],
            client,
            limit=limit,
            candidates=candidates,
            max_per_section=max_per_section,
        )
        search_ms = (time.time() - start) * 1000
        matched = [
            i for i, h in enumerate(hits) if any(_matches(h, e) for e in q.get("expect", []))
        ]
        distinct = {(hits[i]["source"], hits[i]["section"]) for i in matched}
        ok = len(distinct) >= q.get("min_distinct", 1)
        # The fact may also reach the LLM through another chunk (e.g. every chunk of a
        # formation carries "100 % en ligne" in its prefix): expect_text checks that.
        in_context = bool(q.get("expect_text")) and any(
            q["expect_text"].lower() in h["text"].lower()
            for h in hits
            if h["source"] in {e["source"] for e in q.get("expect", [])}
        )
        ok = ok or in_context
        top_score = max((h["score"] for h in hits), default=0.0)
        refused = top_score < threshold
        if q.get("out_of_scope"):
            ok = refused  # an out-of-scope question passes when the threshold refuses it
        results.append(
            {
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
                **({} if q.get("out_of_scope") else context_facts(q, hits)),
                "search_ms": round(search_ms, 1),
                "retrieved": [
                    {"source": h["source"], "section": h["section"], "score": round(h["score"], 3)}
                    for h in hits
                ],
            }
        )

        rank = (
            "hors périmètre"
            if q.get("out_of_scope")
            else f"rang {matched[0] + 1}"
            if matched
            else "fait présent dans le contexte"
            if in_context
            else "absent"
        )
        facts = results[-1].get("facts_in_context")
        print(
            f"{'✅' if ok else '❌'} {q['id']} {q['question'][:70]:70s} {rank}"
            + (f" · faits {facts} {'✅' if results[-1]['context_ok'] else '❌'}" if facts else "")
            + (f", {len(distinct)}/{q['min_distinct']} sections" if q.get("min_distinct") else "")
            + (
                f"  ⛔ refusée (score {top_score:.3f} < {threshold})"
                if refused
                else f"  (score {top_score:.3f})"
                if q.get("out_of_scope")
                else ""
            )
        )
        if verbose or not ok:
            for i, h in enumerate(hits):
                mark = "→" if i in matched else " "
                print(
                    f"     {mark} {h['score']:.3f} {h['source'][:45]:45s} | "
                    f"{(h['section'] or '')[:55]}"
                )
    in_scope = [r for r in results if not r["out_of_scope"]]
    out_scope = [r for r in results if r["out_of_scope"]]
    print(
        f"\nDans le périmètre : {sum(r['passed'] for r in in_scope)}/{len(in_scope)} réussies, "
        f"{sum(bool(r.get('context_ok')) for r in in_scope)}/{len(in_scope)} avec tous les "
        f"faits dans le contexte, "
        f"{sum(r['refused_by_threshold'] for r in in_scope)} refusée(s) à tort par le seuil"
    )
    if out_scope:
        print(
            f"Hors périmètre : {sum(r['passed'] for r in out_scope)}/{len(out_scope)} "
            f"refusées par le seuil"
        )
    if in_scope and out_scope:
        weakest = min(in_scope, key=lambda r: r["top_score"])
        strongest = max(out_scope, key=lambda r: r["top_score"])
        gap = weakest["top_score"] - strongest["top_score"]
        print(
            f"Scores : question légitime la plus faible {weakest['top_score']:.3f} "
            f"({weakest['question_id']}), hors périmètre la plus forte "
            f"{strongest['top_score']:.3f} ({strongest['question_id']}) → écart {gap:+.3f}"
            + (
                f", seuil médian {(weakest['top_score'] + strongest['top_score']) / 2:.3f}"
                if gap > 0
                else " : aucun seuil ne les sépare"
            )
        )
    print(
        f"(limit={limit}, candidates={candidates}, max_per_section={max_per_section}, "
        f"seuil={threshold}, recherche {statistics.median(r['search_ms'] for r in results):.0f}"
        f" ms en médiane)"
    )
    return results


def make_baseline(results: list[dict], config: dict) -> dict:
    """What a later run is compared with: which questions pass, with which settings."""
    return {
        "question_set": QUESTION_SET,
        "config": config,
        "passed": {r["question_id"]: r["passed"] for r in results},
        "context_ok": {r["question_id"]: r["context_ok"] for r in results if "context_ok" in r},
    }


def regressions(results: list[dict], baseline: dict, config: dict) -> list[str]:
    """Reasons why a run is worse than its baseline (empty list: no regression).

    A question that passed and now fails is a regression; one that failed in the baseline may
    stay failed or get fixed. A changed question set or setting is also reported: the
    baseline has to be rewritten on purpose (--write-baseline), not drift silently.
    """
    problems = []
    if baseline["question_set"] != QUESTION_SET:
        problems.append(
            f"question set {QUESTION_SET}, but the baseline has {baseline['question_set']}"
        )
    if baseline["config"] != config:
        problems.append(f"settings {config}, but the baseline has {baseline['config']}")
    now = {r["question_id"]: r["passed"] for r in results}
    for qid, was_ok in baseline["passed"].items():
        if qid not in now:
            problems.append(f"{qid}: in the baseline, not in the run")
        elif was_ok and not now[qid]:
            problems.append(f"{qid}: passed in the baseline, fails now")
    problems += [f"{qid}: not in the baseline" for qid in now if qid not in baseline["passed"]]
    facts_now = {r["question_id"]: r["context_ok"] for r in results if "context_ok" in r}
    for qid, was_ok in baseline.get("context_ok", {}).items():
        if was_ok and not facts_now.get(qid, False):
            problems.append(f"{qid}: facts were in the context in the baseline, not now")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--limit", type=int, default=retrieve.RETRIEVE_LIMIT)
    parser.add_argument("--candidates", type=int, default=retrieve.CANDIDATE_LIMIT)
    parser.add_argument("--max-per-section", type=int, default=retrieve.MAX_PER_SECTION)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--embedding-model", help="override settings.embedding_model")
    parser.add_argument(
        "--max-minutes", type=float, help="time budget for embeddings in this run (resumable)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=GRADE_THRESHOLD,
        help="grading threshold to check refusals against",
    )
    parser.add_argument("--save", metavar="LABEL", help="save the run in eval/results/")
    parser.add_argument("--notes", default="", help="free text saved with the run")
    parser.add_argument(
        "--check",
        metavar="BASELINE",
        type=Path,
        help="exit with 1 when a question that passes in this baseline file now fails",
    )
    parser.add_argument(
        "--write-baseline", metavar="PATH", type=Path, help="write the baseline file and stop"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show every result")
    args = parser.parse_args()
    if args.embedding_model:
        settings.embedding_model = args.embedding_model
    client, info = build_index(args.data, args.chunk_size, args.max_minutes)
    results = evaluate(
        client, args.limit, args.candidates, args.max_per_section, args.verbose, args.threshold
    )

    run_config = {
        "embedding_model": settings.embedding_model,
        "chunk_size": args.chunk_size,
        "limit": args.limit,
        "candidates": args.candidates,
        "max_per_section": args.max_per_section,
        "grade_threshold": args.threshold,
    }
    if args.write_baseline:
        args.write_baseline.write_text(
            json.dumps(make_baseline(results, run_config), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Référence écrite : {args.write_baseline}")
    if args.check:
        problems = regressions(results, json.loads(args.check.read_text()), run_config)
        for problem in problems:
            print(f"RÉGRESSION {problem}")
        if problems:
            sys.exit(1)
        print(f"Aucune régression par rapport à {args.check}")

    if args.save:
        date = dt.date.today().isoformat()
        path = save_run(
            {
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
                    "limit": args.limit,
                    "candidates": args.candidates,
                    "max_per_section": args.max_per_section,
                    "grade_threshold": args.threshold,
                    **info,
                },
                "results": results,
            }
        )
        print(f"Résultats enregistrés : {path}")


if __name__ == "__main__":
    main()
