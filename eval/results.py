"""Evaluation results: one JSON file per run in eval/results/, a shared format.

Every evaluation (retrieval run, end-to-end run on the API, backfilled past tests) is
saved with the same structure, so runs can be compared over time and plotted:

    {
      "schema_version": 1,
      "run_id": "2026-10-02_09_e2e-prod",        # date + sequence + label, sortable
      "date": "2026-10-02",
      "kind": "retrieval" | "e2e",             # chunks retrieved / LLM answers
      "environment": "local" | "prod",
      "git_commit": "adfd056",
      "question_set": "v4",                     # see eval/questions.yaml
      "milestone": true,                        # highlighted in the report
      "label": "...", "notes": "...",
      "config": {...},                          # chunking, retrieval, models, versions
      "summary": {"total": 16, "passed": 14, ...},
      "results": [{"question_id": "q01", ...}, ...]
    }

Per-question fields: `passed`, and for retrieval `rank` (1-based, null when absent),
`distinct_sections`, `top_score`, `refused_by_threshold`; for e2e `answer`,
`sources`, `latency_s`, `verdict` (correct | partial | wrong | refused | no_answer |
error), `auto_check`, and `edge_cases` (ids from eval/edge_cases.yaml).
"""
import json
import re
import subprocess
from pathlib import Path

import yaml

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
QUESTIONS = EVAL_DIR / "questions.yaml"
QUESTION_SET = "v4"
SCHEMA_VERSION = 1

VERDICTS = ("correct", "partial", "wrong", "refused", "no_answer", "error")
# The LLM says it cannot answer from the context (prompt: "dis-le honnêtement").
_NO_ANSWER = re.compile(
    r"ne (contient|mentionne|précise) pas|pas d'information|ne peux (donc )?pas répondre",
    re.IGNORECASE,
)


def load_questions() -> list[dict]:
    questions: list[dict] = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    return questions


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, check=True, cwd=EVAL_DIR)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, cwd=EVAL_DIR).stdout.strip()
        return out.stdout.strip() + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def check_answer(question: dict, answer: str, refused: bool = False) -> dict:
    """Apply the question's answer_must / answer_must_not regexes to an LLM answer.

    Returns {"must": {regex: bool}, "must_not_hits": [regex], "verdict": str}.
    """
    text = re.sub(r"[\s  ]+", " ", answer.replace("**", ""))
    must = {p: bool(re.search(p, text, re.IGNORECASE)) for p in question.get("answer_must", [])}
    must_not_hits = [p for p in question.get("answer_must_not", [])
                     if re.search(p, text, re.IGNORECASE)]
    if refused:
        verdict = "refused"
    elif must_not_hits:
        verdict = "wrong"
    elif must and all(must.values()):
        verdict = "correct"
    elif any(must.values()):
        verdict = "partial"
    elif _NO_ANSWER.search(text):
        verdict = "no_answer"
    else:
        verdict = "wrong"
    return {"must": must, "must_not_hits": must_not_hits, "verdict": verdict}


def summarize(kind: str, results: list[dict]) -> dict:
    summary: dict = {"total": len(results), "passed": sum(bool(r["passed"]) for r in results)}
    if kind == "retrieval":
        summary["refused_by_threshold"] = sum(bool(r.get("refused_by_threshold"))
                                              for r in results)
    else:
        for verdict in VERDICTS:
            summary[verdict] = sum(r.get("verdict") == verdict for r in results)
    return summary


def next_run_id(date: str, label: str) -> str:
    existing = list(RESULTS_DIR.glob(f"{date}_*.json"))
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return f"{date}_{len(existing) + 1:02d}_{slug}"


def save_run(run: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    run = {"schema_version": SCHEMA_VERSION, **run}
    run["summary"] = summarize(run["kind"], run["results"])
    path = RESULTS_DIR / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_runs() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(RESULTS_DIR.glob("*.json"))]
