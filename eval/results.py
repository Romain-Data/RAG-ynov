"""Evaluation results: one JSON file per run in eval/results/, a shared format.

Every evaluation (retrieval run, end-to-end run on the API, backfilled past tests) is
saved with the same structure, so runs can be compared over time and plotted:

    {
      "schema_version": 1,
      "run_id": "2026-10-02_09_e2e-prod",        # date + sequence + label, sortable
      "date": "2026-10-02",
      "kind": "retrieval" | "e2e" | "conversation",  # chunks / LLM answers / multi-turn answers
      "environment": "local" | "preprod" | "prod",
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
error), `auto_check`, and `edge_cases` (ids from eval/edge_cases.yaml). A conversation run
has one result per turn (`question_id` "c01.2", `conversation`, `turn`, `rewritten`).
"""

import json
import re
import subprocess
from pathlib import Path

import yaml

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
QUESTIONS = EVAL_DIR / "questions.yaml"
QUESTION_SET = "v9"
CONVERSATIONS = EVAL_DIR / "conversations.yaml"
CONVERSATION_SET = "c2"
SCHEMA_VERSION = 1

VERDICTS = ("correct", "partial", "wrong", "refused", "no_answer", "error")
# The LLM says it cannot answer from the context (prompt: "dis-le honnêtement").
_NO_ANSWER = re.compile(
    r"ne (contient|mentionne|précise) pas|pas mentionnée?s?|pas d'information"
    r"|ne peux (donc )?pas répondre|ne peux répondre qu'aux questions"
    r"|uniquement (aux|sur les) questions",
    re.IGNORECASE,
)


def load_questions() -> list[dict]:
    questions: list[dict] = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    return questions


def load_conversations() -> list[dict]:
    conversations: list[dict] = yaml.safe_load(CONVERSATIONS.read_text(encoding="utf-8"))
    return conversations


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=EVAL_DIR,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            cwd=EVAL_DIR,
        ).stdout.strip()
        return out.stdout.strip() + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def check_answer(question: dict, answer: str, refused: bool = False) -> dict:
    """Apply the question's answer_must / answer_must_not regexes to an LLM answer.

    Returns {"must": {regex: bool}, "must_not_hits": [regex], "verdict": str}.
    """
    text = re.sub(r"[\s  ]+", " ", answer.replace("**", ""))
    must = {p: bool(re.search(p, text, re.IGNORECASE)) for p in question.get("answer_must", [])}
    must_not_hits = [
        p for p in question.get("answer_must_not", []) if re.search(p, text, re.IGNORECASE)
    ]
    if question.get("out_of_scope"):
        # Nothing to answer: refusing (threshold) or declining (LLM) is the right outcome
        verdict = "correct" if refused or _NO_ANSWER.search(text) else "wrong"
    elif refused:
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
        # In-scope questions refused by the threshold are errors; out-of-scope ones
        # refused are the expected outcome, counted apart.
        summary["refused_by_threshold"] = sum(
            bool(r.get("refused_by_threshold")) and not r.get("out_of_scope") for r in results
        )
        summary["out_of_scope_refused"] = sum(
            bool(r.get("refused_by_threshold")) and bool(r.get("out_of_scope")) for r in results
        )
        # Score gap used to calibrate the grading threshold of an embedding model
        in_tops = [
            r["top_score"]
            for r in results
            if not r.get("out_of_scope") and r.get("top_score") is not None
        ]
        out_tops = [
            r["top_score"]
            for r in results
            if r.get("out_of_scope") and r.get("top_score") is not None
        ]
        if in_tops and out_tops:
            summary["in_scope_min_top_score"] = min(in_tops)
            summary["out_of_scope_max_top_score"] = max(out_tops)
    else:
        for verdict in VERDICTS:
            summary[verdict] = sum(r.get("verdict") == verdict for r in results)
        # Out-of-scope questions only check that nothing is answered: count them apart
        in_scope = [r for r in results if not r.get("out_of_scope")]
        if len(in_scope) < len(results):
            summary["in_scope_total"] = len(in_scope)
            summary["in_scope_correct"] = sum(r.get("verdict") == "correct" for r in in_scope)
            summary["out_of_scope_total"] = len(results) - len(in_scope)
            summary["out_of_scope_correct"] = sum(
                r.get("verdict") == "correct" for r in results if r.get("out_of_scope")
            )
    return summary


def next_run_id(date: str, label: str) -> str:
    """<date>_<sequence>_<label>: the sequence follows the highest one of the day, not the
    number of files, which gave a sequence twice after a run file was deleted."""
    sequences = [
        int(match.group(1))
        for path in RESULTS_DIR.glob(f"{date}_*.json")
        if (match := re.match(rf"{re.escape(date)}_(\d+)_", path.name))
    ]
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return f"{date}_{max(sequences, default=0) + 1:02d}_{slug}"


def save_run(run: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    run = {"schema_version": SCHEMA_VERSION, **run}
    run["summary"] = summarize(run["kind"], run["results"])
    path = RESULTS_DIR / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_runs() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS_DIR.glob("*.json"))]
