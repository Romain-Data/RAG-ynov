"""End-to-end evaluation: ask the questions to a running API and check the answers.

Each answer is checked against the `answer_must` / `answer_must_not` regexes of
eval/questions.yaml, which gives an automatic verdict (correct, partial, wrong,
refused, no_answer, error). The run is saved in eval/results/ with the full answers
and sources; a reviewer can then correct a verdict by editing `verdict` (and adding
`review_note`) in the JSON file, the automatic one stays in `auto_check`.

With --local, the graph runs in process instead of over HTTP: retrieval uses the
local evaluation index (.eval_qdrant/, built like eval/retrieval.py) and generation
calls the LLM configured in .env. This tests code changes (prompt, threshold) before
deploying them.

Usage:
    uv run python -m eval.e2e --save "label" [--url https://rag.romaincollery.com]
    uv run python -m eval.e2e --local --save "label"
    uv run python -m eval.e2e --local --conversations --save "label"

With --conversations (local only), the scenarios of eval/conversations.yaml are played
through the conversation graph (graph/chat.py): each turn is asked with the previous
turns as history, and the standalone rewrite of the question is saved for review.
"""

import argparse
import atexit
import datetime as dt
import os
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from eval.results import (
    CONVERSATION_SET,
    QUESTION_SET,
    check_answer,
    git_commit,
    load_conversations,
    load_questions,
    next_run_id,
    save_run,
)

DEFAULT_URL = "https://rag.romaincollery.com"
RATE_LIMIT_PAUSE_S = 2.5  # /api/query allows 30 requests per minute per IP


Answer = tuple[dict | None, float, str | None]  # (response, latency in s, error)


def ask(url: str, question: str) -> Answer:
    start = time.time()
    try:
        # The preprod sits behind a password (SITE_PASSWORD on the server)
        password = os.environ.get("EVAL_SITE_PASSWORD")
        resp = httpx.post(
            f"{url}/api/query",
            json={"question": question},
            timeout=120,
            auth=("preprod", password) if password else None,
        )
        resp.raise_for_status()
        return resp.json(), time.time() - start, None
    except httpx.HTTPError as exc:
        return None, time.time() - start, str(exc)


def local_asker(
    data_dir: Path,
    embedding_model: str | None = None,
    threshold: float | None = None,
    chunk_size: int | None = None,
    conversations: bool = False,
) -> tuple[Callable[..., Answer], dict]:
    """Run the graph in process on the local evaluation index. Returns (ask, config).

    embedding_model, threshold and chunk_size override the configured values, to test
    another embedding model end to end (its index must be built: eval/retrieval.py).
    With `conversations`, ask takes the list of messages and runs the conversation graph
    (graph/chat.py) instead of a question and the single-question graph.
    """
    from app.core.config import settings
    from eval.retrieval import build_index
    from graph import builder, chat
    from graph.nodes import grade, retrieve
    from ingestion.chunking import CHUNK_SIZE

    if embedding_model:
        settings.embedding_model = embedding_model
    if threshold is not None:
        grade.GRADE_THRESHOLD = threshold
    chunk_size = chunk_size or CHUNK_SIZE
    client, info = build_index(data_dir, chunk_size)
    atexit.register(client.close)  # avoids a noisy error when the interpreter exits
    retrieve.get_qdrant_client = lambda: client
    graph = chat.build_chat_graph() if conversations else builder.build_graph()

    def ask_local(question_or_messages: str | list[dict]) -> Answer:
        start = time.time()
        try:
            if conversations:
                state = graph.invoke({"messages": question_or_messages})
            else:
                state = graph.invoke({"question": question_or_messages})
            return (
                {
                    "answer": state.get("answer", ""),
                    "sources": state.get("sources", []),
                    "rewritten": state.get("rewritten"),
                },
                time.time() - start,
                None,
            )
        except (httpx.HTTPError, KeyError) as exc:  # LLM call failed
            return None, time.time() - start, str(exc)

    config = {
        "mode": "local graph",
        "llm_model": settings.mammouth_chat_model,
        "embedding_model": settings.embedding_model,
        "chunk_size": chunk_size,
        "n_chunks": info["n_chunks"],
        "limit": retrieve.RETRIEVE_LIMIT,
        "candidates": retrieve.CANDIDATE_LIMIT,
        "max_per_section": retrieve.MAX_PER_SECTION,
        "grade_threshold": grade.GRADE_THRESHOLD,
    }
    return ask_local, config


def run(ask_fn: Callable[[str], Answer], ids: set[str] | None, pause: float) -> list[dict]:
    results = []
    for q in load_questions():
        if ids and q["id"] not in ids:
            continue
        data, latency, error = ask_fn(q["question"])
        if data is None:
            result = {
                "question_id": q["id"],
                "question": q["question"],
                "passed": False,
                "verdict": "error",
                "error": error,
                "latency_s": round(latency, 2),
            }
        else:
            # The API answers with no source when the grading threshold refuses the
            # question: the LLM is not called.
            refused = not data["sources"]
            check = check_answer(q, data["answer"], refused=refused)
            result = {
                "question_id": q["id"],
                "question": q["question"],
                "out_of_scope": q.get("out_of_scope"),
                "passed": check["verdict"] == "correct",
                "verdict": check["verdict"],
                "auto_check": check,
                "answer": data["answer"].strip(),
                "sources": data["sources"],
                "latency_s": round(latency, 2),
                "edge_cases": [],
            }
        results.append(result)
        print(f"{result['verdict']:9s} {q['id']} {q['question'][:80]}  ({result['latency_s']}s)")
        time.sleep(pause)
    return results


def run_conversations(
    ask_fn: Callable[[list[dict]], Answer], ids: set[str] | None, pause: float
) -> list[dict]:
    """Play every scenario of eval/conversations.yaml, one result per turn."""
    results = []
    for scenario in load_conversations():
        if ids and scenario["id"] not in ids:
            continue
        messages: list[dict] = []
        for number, turn in enumerate(scenario["turns"], start=1):
            messages.append({"role": "user", "content": turn["question"]})
            data, latency, error = ask_fn(messages)
            result_id = f"{scenario['id']}.{number}"
            base = {
                "question_id": result_id,
                "conversation": scenario["id"],
                "turn": number,
                "question": turn["question"],
                "out_of_scope": turn.get("out_of_scope"),
                "latency_s": round(latency, 2),
            }
            if data is None:
                result = {**base, "passed": False, "verdict": "error", "error": error}
            else:
                check = check_answer(turn, data["answer"], refused=not data["sources"])
                result = {
                    **base,
                    "passed": check["verdict"] == "correct",
                    "verdict": check["verdict"],
                    "auto_check": check,
                    "rewritten": data.get("rewritten"),
                    "answer": data["answer"].strip(),
                    "sources": data["sources"],
                    "edge_cases": [],
                }
                messages.append({"role": "assistant", "content": data["answer"].strip()})
            results.append(result)
            print(
                f"{result['verdict']:9s} {result_id} {turn['question'][:60]}"
                f"  -> {data.get('rewritten') if data else '?'}  ({result['latency_s']}s)"
            )
            if data is None:
                break  # the next turns would miss this answer in their history
            time.sleep(pause)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--ids", help="comma-separated question ids (default: all)")
    parser.add_argument(
        "--local",
        action="store_true",
        help="run the graph in process on the local evaluation index",
    )
    parser.add_argument(
        "--conversations",
        action="store_true",
        help="--local only: play eval/conversations.yaml (multi-turn)",
    )
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--embedding-model", help="--local only: override the model")
    parser.add_argument("--threshold", type=float, help="--local only: grading threshold")
    parser.add_argument("--chunk-size", type=int, help="--local only: chunk size")
    parser.add_argument("--environment", default=None, help="default: prod, or local")
    parser.add_argument("--save", metavar="LABEL", help="save the run in eval/results/")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    if args.conversations and not args.local:
        parser.error("--conversations needs --local")
    ids = set(args.ids.split(",")) if args.ids else None
    if args.local:
        ask_fn, config = local_asker(
            args.data,
            args.embedding_model,
            args.threshold,
            args.chunk_size,
            conversations=args.conversations,
        )
        if args.conversations:
            results = run_conversations(ask_fn, ids, pause=0.5)
        else:
            results = run(ask_fn, ids, pause=0.5)
    else:
        config = {"url": args.url}
        results = run(lambda question: ask(args.url, question), ids, RATE_LIMIT_PAUSE_S)
    correct = sum(r["verdict"] == "correct" for r in results)
    print(f"\n{correct}/{len(results)} réponses correctes (vérification automatique)")

    if args.save:
        date = dt.date.today().isoformat()
        path = save_run(
            {
                "run_id": next_run_id(date, args.save),
                "date": date,
                "kind": "conversation" if args.conversations else "e2e",
                "environment": args.environment or ("local" if args.local else "prod"),
                "git_commit": git_commit(),
                "question_set": CONVERSATION_SET if args.conversations else QUESTION_SET,
                "milestone": False,
                "label": args.save,
                "notes": args.notes,
                "config": config,
                "results": results,
            }
        )
        print(f"Résultats enregistrés : {path}")


if __name__ == "__main__":
    main()
