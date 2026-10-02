"""End-to-end evaluation: ask the questions to a running API and check the answers.

Each answer is checked against the `answer_must` / `answer_must_not` regexes of
eval/questions.yaml, which gives an automatic verdict (correct, partial, wrong,
refused, no_answer, error). The run is saved in eval/results/ with the full answers
and sources; a reviewer can then correct a verdict by editing `verdict` (and adding
`review_note`) in the JSON file, the automatic one stays in `auto_check`.

Usage:
    uv run python -m eval.e2e --save "label" [--url https://rag.romaincollery.com]
"""
import argparse
import datetime as dt
import time

import httpx

from eval.results import (
    QUESTION_SET,
    check_answer,
    git_commit,
    load_questions,
    next_run_id,
    save_run,
)

DEFAULT_URL = "https://rag.romaincollery.com"
RATE_LIMIT_PAUSE_S = 2.5  # /api/query allows 30 requests per minute per IP


def ask(url: str, question: str) -> tuple[dict | None, float, str | None]:
    start = time.time()
    try:
        resp = httpx.post(f"{url}/api/query", json={"question": question}, timeout=120)
        resp.raise_for_status()
        return resp.json(), time.time() - start, None
    except httpx.HTTPError as exc:
        return None, time.time() - start, str(exc)


def run(url: str, ids: set[str] | None) -> list[dict]:
    results = []
    for q in load_questions():
        if ids and q["id"] not in ids:
            continue
        data, latency, error = ask(url, q["question"])
        if data is None:
            result = {"question_id": q["id"], "question": q["question"], "passed": False,
                      "verdict": "error", "error": error, "latency_s": round(latency, 2)}
        else:
            # The API answers with no source when the grading threshold refuses the
            # question: the LLM is not called.
            refused = not data["sources"]
            check = check_answer(q, data["answer"], refused=refused)
            result = {
                "question_id": q["id"],
                "question": q["question"],
                "passed": check["verdict"] == "correct",
                "verdict": check["verdict"],
                "auto_check": check,
                "answer": data["answer"].strip(),
                "sources": data["sources"],
                "latency_s": round(latency, 2),
                "edge_cases": [],
            }
        results.append(result)
        print(f"{result['verdict']:9s} {q['id']} {q['question'][:80]}  "
              f"({result['latency_s']}s)")
        time.sleep(RATE_LIMIT_PAUSE_S)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--ids", help="comma-separated question ids (default: all)")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--save", metavar="LABEL", help="save the run in eval/results/")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    results = run(args.url, set(args.ids.split(",")) if args.ids else None)
    correct = sum(r["verdict"] == "correct" for r in results)
    print(f"\n{correct}/{len(results)} réponses correctes (vérification automatique)")

    if args.save:
        date = dt.date.today().isoformat()
        path = save_run({
            "run_id": next_run_id(date, args.save),
            "date": date,
            "kind": "e2e",
            "environment": args.environment,
            "git_commit": git_commit(),
            "question_set": QUESTION_SET,
            "milestone": False,
            "label": args.save,
            "notes": args.notes,
            "config": {"url": args.url},
            "results": results,
        })
        print(f"Résultats enregistrés : {path}")


if __name__ == "__main__":
    main()
