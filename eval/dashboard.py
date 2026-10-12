"""Figures of the evaluation dashboard (#16), shared by /admin/tableau-de-bord and
eval/REPORT.md: computed from eval/results/*.json, eval/questions.yaml and
eval/edge_cases.yaml, so that each figure has a single definition.

Plain functions over the list of runs, without FastAPI: another page (a public one, a file)
could reuse them. Scores come from the verdicts as reviewed by hand, never from the
`summary` saved with the run (it is not recomputed when a verdict is corrected) nor from
`auto_check`.

Never import eval.retrieval here: it puts a fake Mammouth key in the environment, which the
API importing this module would then use for every answer.
"""

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

import yaml

from eval import results
from eval.results import EVAL_DIR, SCHEMA_VERSION, summarize

EDGE_CASES = EVAL_DIR / "edge_cases.yaml"
KINDS = ("retrieval", "e2e", "conversation")
ENVIRONMENTS = {"local": "local", "preprod": "préprod", "prod": "prod"}
# The questions asked since the first runs (v4): the only score comparable from end to end
REFERENCE_IDS = tuple(f"q{n:02d}" for n in range(1, 17))
VERDICT_ICONS = {
    "correct": "✅",
    "partial": "🟡",
    "wrong": "❌",
    "refused": "⛔",
    "no_answer": "∅",
    "error": "⚠️",
}
VERDICT_LABELS = {
    "correct": "correcte",
    "partial": "partielle",
    "wrong": "fausse",
    "refused": "refusée au seuil",
    "no_answer": "sans réponse",
    "error": "erreur",
}
STATUS_LABELS = {
    "open": "🔴 ouvert",
    "mitigated": "🟠 atténué",
    "fixed": "🟢 corrigé",
    "lesson": "📘 enseignement",
    "wontfix": "⚪ abandonné",
}


# --- Loading ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Loaded:
    runs: list[dict]  # the readable runs, in the order of their file names (run ids)
    skipped: list[tuple[str, str]]  # (file name, reason) of the files left out


_cache: dict[Path, tuple[tuple, Loaded]] = {}


def _problem(run: object) -> str | None:
    """Why `run` cannot be shown, or None when it can."""
    if not isinstance(run, dict):
        return "pas un objet JSON"
    if run.get("schema_version") != SCHEMA_VERSION:
        return f"version de format inconnue ({run.get('schema_version')!r})"
    if not isinstance(run.get("run_id"), str) or not isinstance(run.get("date"), str):
        return "identifiant ou date manquant"
    if run.get("kind") not in KINDS:
        return f"type inconnu ({run.get('kind')!r})"
    if not isinstance(run.get("environment"), str):
        return "environnement manquant"
    if not isinstance(run.get("config", {}), dict):
        return "configuration illisible"
    lines = run.get("results")
    if not isinstance(lines, list) or not all(
        isinstance(line, dict) and isinstance(line.get("question_id"), str) and "passed" in line
        for line in lines
    ):
        return "résultats illisibles"
    return None


def load_runs(directory: Path | None = None) -> Loaded:
    """The runs of `directory` (eval/results/ by default). A file that cannot be read, or of
    another format, is left out and listed in `skipped`, never an error. Kept in memory while
    the names, sizes and dates of the files stay the same (in production they only change
    with a deployment)."""
    directory = directory or results.RESULTS_DIR  # read at call time: the tests patch it
    try:
        paths = sorted(directory.glob("*.json"))
        key = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    except OSError:
        paths, key = [], ()
    cached = _cache.get(directory)
    if cached is not None and cached[0] == key:
        return cached[1]
    runs: list[dict] = []
    skipped: list[tuple[str, str]] = []
    for path in paths:
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            skipped.append((path.name, "JSON illisible"))
            continue
        if (problem := _problem(run)) is not None:
            skipped.append((path.name, problem))
            continue
        runs.append(run)
    loaded = Loaded(runs, skipped)
    _cache[directory] = (key, loaded)
    return loaded


def _yaml_list(path: Path) -> tuple[list[dict], str | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [], f"{path.name} : {type(exc).__name__}"
    if not isinstance(data, list):
        return [], f"{path.name} : pas une liste"
    return [item for item in data if isinstance(item, dict) and "id" in item], None


@dataclass(frozen=True)
class Data:
    runs: list[dict]
    questions: list[dict]  # eval/questions.yaml
    edge_cases: list[dict]  # eval/edge_cases.yaml
    problems: list[str]  # what could not be read, to say so on the page


def load(directory: Path | None = None) -> Data:
    loaded = load_runs(directory)
    questions, questions_problem = _yaml_list(results.QUESTIONS)
    cases, cases_problem = _yaml_list(EDGE_CASES)
    problems = [f"{name} : {reason}" for name, reason in loaded.skipped]
    problems += [p for p in (questions_problem, cases_problem) if p]
    return Data(loaded.runs, questions, cases, problems)


# --- One run ------------------------------------------------------------------------------------


def short_id(run: dict) -> str:
    """Month-day and sequence of a run id ("10-03_02"): the sequence restarts every day."""
    return str(run["run_id"][5:13])


def _config(run: dict, key: str, server_key: str | None = None) -> object | None:
    """A value of the run's configuration, else of the server's answer to /api/health that
    eval.e2e records since #16 (`config.server`)."""
    config = run.get("config") or {}
    value = config.get(key)
    server = config.get("server")
    if value is None and isinstance(server, dict):
        value = server.get(server_key or key)
    return value


def model(run: dict) -> str | None:
    """The LLM of the run: `llm_model` (local runs, and server runs since #16), else the
    alias the server announced, else unknown. Retrieval runs have none."""
    value = _config(run, "llm_model", "chat_model")
    return str(value) if value else None


def collection(run: dict) -> str | None:
    value = _config(run, "collection")
    return str(value) if value else None


def threshold(run: dict) -> float | None:
    value = _config(run, "grade_threshold")
    return float(value) if isinstance(value, int | float) else None


def version(run: dict) -> str | None:
    """The code that answered: the commit of the server for a server run (when it gives
    one), the commit of the machine for a local run."""
    if run["environment"] == "local":
        return run.get("git_commit") or None
    value = _config(run, "server_version", "version")
    return str(value) if value else None


def reconstructed(run: dict, key: str) -> bool:
    """Whether a value of the configuration was filled in afterwards from the documented
    history (#16: `<key>_source: "reconstitué"`), not recorded by the run itself."""
    return (run.get("config") or {}).get(f"{key}_source") == "reconstitué"


def score(run: dict) -> dict:
    """The counts of a run (eval/results.py::summarize), recomputed from the reviewed verdicts."""
    return summarize(run["kind"], run["results"])


@dataclass(frozen=True)
class Quality:
    in_scope_ok: int  # Ynov questions answered right (e2e) or retrieved (retrieval)
    in_scope_total: int
    out_of_scope_ok: int  # out-of-scope questions declined or refused
    out_of_scope_total: int
    wrong: int  # answers judged wrong (e2e), 0 for retrieval
    refused: int  # Ynov questions refused by the threshold
    reference_ok: int | None  # right among q01-q16, None when one of them was not asked


def _ok(run: dict, line: dict) -> bool:
    if run["kind"] == "retrieval":
        return bool(line.get("passed"))
    return line.get("verdict") == "correct"


def quality(run: dict) -> Quality:
    s = score(run)
    by_id = {line["question_id"]: line for line in run["results"]}
    reference = (
        sum(_ok(run, by_id[qid]) for qid in REFERENCE_IDS)
        if all(qid in by_id for qid in REFERENCE_IDS)
        else None
    )
    if run["kind"] == "retrieval":
        in_scope = [line for line in run["results"] if not line.get("out_of_scope")]
        out_scope = [line for line in run["results"] if line.get("out_of_scope")]
        return Quality(
            in_scope_ok=sum(bool(line.get("passed")) for line in in_scope),
            in_scope_total=len(in_scope),
            out_of_scope_ok=sum(bool(line.get("passed")) for line in out_scope),
            out_of_scope_total=len(out_scope),
            wrong=0,
            refused=s.get("refused_by_threshold", 0),
            reference_ok=reference,
        )
    return Quality(
        in_scope_ok=s.get("in_scope_correct", s["correct"]),
        in_scope_total=s.get("in_scope_total", s["total"]),
        out_of_scope_ok=s.get("out_of_scope_correct", 0),
        out_of_scope_total=s.get("out_of_scope_total", 0),
        wrong=s["wrong"],
        refused=s["refused"],
        reference_ok=reference,
    )


def median_latency(run: dict) -> float | None:
    """Median time to answer a question, in seconds (errors left out), for answer runs."""
    times = [
        float(line["latency_s"])
        for line in run["results"]
        if isinstance(line.get("latency_s"), int | float) and line.get("verdict") != "error"
    ]
    return statistics.median(times) if times else None


@dataclass(frozen=True)
class Margins:
    """The extreme scores of a retrieval run: the lowest Ynov question must stay above the
    threshold, the highest out-of-scope question below it."""

    in_scope_min: float
    out_of_scope_max: float
    threshold: float | None

    @property
    def gap(self) -> float:
        """Room for a threshold: negative, no threshold separates the two."""
        return self.in_scope_min - self.out_of_scope_max


def margins(run: dict) -> Margins | None:
    if run["kind"] != "retrieval":
        return None
    s = score(run)
    if "in_scope_min_top_score" not in s:
        return None
    return Margins(s["in_scope_min_top_score"], s["out_of_scope_max_top_score"], threshold(run))


def mark(run: dict, line: dict | None) -> str:
    """The cell of a question in a run: the verdict of an answer, or for retrieval the rank
    of the right section (✅ ctx: the fact reached the context), ⛔ refused by the threshold."""
    if line is None:
        return "·"
    if run["kind"] in ("e2e", "conversation"):
        return VERDICT_ICONS.get(line.get("verdict", ""), "?")
    if line.get("in_context") and not line.get("rank"):
        text = "✅ ctx"
    elif line.get("passed"):
        # An out-of-scope question passes with no rank: it had nothing to retrieve
        text = f"✅ {line['rank']}" if line.get("rank") else "✅"
    else:
        text = "❌" + (f" {line['rank']}" if line.get("rank") else "")
    if line.get("min_distinct", 1) > 1:
        text += f" ({line.get('distinct_sections')}/{line['min_distinct']})"
    if line.get("refused_by_threshold"):
        text += " ⛔"
    return text


# --- Several runs ------------------------------------------------------------------------------


def select(
    runs: list[dict],
    kind: str,
    environment: str = "",
    milestones_only: bool = False,
) -> list[dict]:
    """The runs of a kind, of one environment ("" for all), optionally the milestones only."""
    return [
        run
        for run in runs
        if run["kind"] == kind
        and (not environment or run["environment"] == environment)
        and (not milestones_only or run.get("milestone"))
    ]


def latest(runs: list[dict], kind: str, environment: str = "") -> dict | None:
    chosen = select(runs, kind, environment)
    return chosen[-1] if chosen else None


def _show(value: object) -> str:
    return f"{value:g}".replace(".", ",") if isinstance(value, float) else str(value)


def _tracked(run: dict) -> list[tuple[str, object | None]]:
    return [
        ("jeu", run.get("question_set") or None),
        ("modèle", model(run)),
        ("collection", collection(run)),
        ("seuil", threshold(run)),
    ]


def changes(runs: list[dict]) -> dict[str, list[str]]:
    """What changed since the previous run of the same kind and environment, by run id:
    question set, LLM, collection, threshold ("modèle mistral-medium-3-5 → …"). Compared
    with the last known value: a run that does not record one (the server runs before #16)
    neither starts nor ends a change."""
    last: dict[tuple[str, str, str], object] = {}
    found: dict[str, list[str]] = {}
    for run in runs:
        lines = []
        for label, value in _tracked(run):
            if value is None:
                continue
            slot = (run["kind"], run["environment"], label)
            before = last.get(slot)
            if before is not None and before != value:
                lines.append(f"{label} {_show(before)} → {_show(value)}")
            last[slot] = value
        if lines:
            found[run["run_id"]] = lines
    return found


@dataclass(frozen=True)
class Cell:
    state: str  # a verdict, or for retrieval "ok" / "ko"; "absent" when not asked
    text: str  # what eval/REPORT.md shows (mark)
    tip: str  # verdict in words and review note


@dataclass(frozen=True)
class Row:
    question_id: str
    question: str
    out_of_scope: bool
    edge_cases: list[str]
    cells: list[Cell]


def _cell(run: dict, line: dict | None) -> Cell:
    if line is None:
        return Cell("absent", "·", "question absente de ce passage")
    text = mark(run, line)
    note = str(line.get("review_note") or "").strip()
    if run["kind"] == "retrieval":
        state = "ok" if line.get("passed") else "ko"
        tip = "retrouvée" if line.get("passed") else "non retrouvée"
        if line.get("rank"):
            tip += f", rang {line['rank']}"
        if line.get("refused_by_threshold"):
            tip += ", refusée au seuil"
    else:
        state = str(line.get("verdict", "?"))
        tip = VERDICT_LABELS.get(state, state)
    return Cell(state, text, f"{tip} — {note}" if note else tip)


def matrix(runs: list[dict], questions: list[dict], edge_cases: list[dict]) -> list[Row]:
    """One row per question of questions.yaml (Ynov questions first, then out of scope), then
    the questions of the runs that are no longer in it; one cell per run."""
    cases_of: dict[str, list[str]] = {}
    for case in edge_cases:
        for qid in case.get("questions") or []:
            cases_of.setdefault(str(qid), []).append(str(case["id"]))
    by_run = [{line["question_id"]: line for line in run["results"]} for run in runs]
    known = [
        (str(q["id"]), str(q.get("question", "")), bool(q.get("out_of_scope"))) for q in questions
    ]
    ids = {qid for qid, _, _ in known}
    extra: dict[str, tuple[str, bool]] = {}
    for lines in by_run:
        for qid, line in lines.items():
            if qid not in ids and qid not in extra:
                extra[qid] = (str(line.get("question", "")), bool(line.get("out_of_scope")))
    ordered = (
        [q for q in known if not q[2]]
        + [q for q in known if q[2]]
        + [(qid, text, oos) for qid, (text, oos) in extra.items()]
    )
    return [
        Row(
            question_id=qid,
            question=text,
            out_of_scope=oos,
            edge_cases=cases_of.get(qid, []),
            cells=[_cell(run, lines.get(qid)) for run, lines in zip(runs, by_run, strict=True)],
        )
        for qid, text, oos in ordered
    ]


def edge_case_counts(edge_cases: list[dict]) -> dict[str, int]:
    """Number of edge cases per status, in the order of STATUS_LABELS (an unknown status
    comes after)."""
    counts = dict.fromkeys(STATUS_LABELS, 0)
    for case in edge_cases:
        status = str(case.get("status", "?"))
        counts[status] = counts.get(status, 0) + 1
    return counts


@dataclass(frozen=True)
class Agreement:
    agree: int
    reviewed: int
    # (run id, question id, reviewed verdict, automatic verdict)
    disagreements: list[tuple[str, str, str, str]]


def auto_check_agreement(runs: list[dict]) -> Agreement:
    """How often the automatic check (answer_must) gives the verdict of the review, over the
    answers of the end-to-end runs."""
    agree, reviewed, disagreements = 0, 0, []
    for run in runs:
        if run["kind"] != "e2e":
            continue
        for line in run["results"]:
            auto = line.get("auto_check")
            if not isinstance(auto, dict):
                continue
            reviewed += 1
            if auto.get("verdict") == line.get("verdict"):
                agree += 1
            else:
                disagreements.append(
                    (
                        run["run_id"],
                        line["question_id"],
                        str(line.get("verdict")),
                        str(auto.get("verdict")),
                    )
                )
    return Agreement(agree, reviewed, disagreements)
