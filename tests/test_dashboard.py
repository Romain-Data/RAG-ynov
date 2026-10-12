"""Tests for the figures of the evaluation dashboard (#16, eval/dashboard.py) and its inline
SVG charts (admin/charts.py), on fictitious runs (no LLM, no Qdrant)."""

import json
import os
from pathlib import Path

import pytest

from admin import charts
from eval import dashboard, report, results

QUESTIONS = [{"id": f"q{n:02d}", "question": f"Question {n} ?"} for n in range(1, 17)] + [
    {"id": "q17", "question": "Quelle est la capitale de l'Australie ?", "out_of_scope": "llm"}
]
CASES = [
    {"id": "EC-01", "title": "Un cas", "status": "fixed", "questions": ["q02", "q05"]},
    {"id": "EC-02", "title": "Un autre", "status": "open", "questions": ["q02"]},
    {"id": "EC-03", "title": "Une leçon", "status": "lesson", "questions": []},
]


def line(qid: str, verdict: str = "correct", **extra) -> dict:
    out = {"question_id": qid, "question": f"Q {qid}", "verdict": verdict, "passed": True}
    return {**out, **extra}


def run(run_id: str, kind: str = "e2e", environment: str = "local", **extra) -> dict:
    out = {
        "schema_version": results.SCHEMA_VERSION,
        "run_id": run_id,
        "date": run_id[:10],
        "kind": kind,
        "environment": environment,
        "git_commit": "1234abc",
        "question_set": "v5",
        "milestone": False,
        "label": run_id[14:],
        "config": {},
        "summary": {},
        "results": [],
    }
    return {**out, **extra}


def sixteen(wrong: tuple[str, ...] = ()) -> list[dict]:
    """q01 to q16, right but for `wrong`, and q17 out of scope (declined)."""
    lines = [
        line(f"q{n:02d}", "wrong" if f"q{n:02d}" in wrong else "correct") for n in range(1, 17)
    ]
    return lines + [line("q17", out_of_scope="llm")]


RUNS = [
    # The first prod run: six questions, no configuration
    run(
        "2026-10-01_01_prod-six",
        environment="prod",
        question_set="v4",
        config={"url": "https://rag.example"},
        results=[line(f"q{n:02d}") for n in range(1, 7)],
    ),
    run(
        "2026-10-02_01_local-a",
        milestone=True,
        config={"llm_model": "model-a", "grade_threshold": 0.45},
        # The summary saved with the run says 15: a verdict was corrected afterwards
        summary={"total": 17, "correct": 15},
        results=[
            *sixteen(),
            line("q99", "partial", question="Une question retirée du jeu ?"),
        ],
    ),
    run(
        "2026-10-03_01_local-b",
        question_set="v6",
        config={"llm_model": "model-b", "grade_threshold": 0.47},
        results=[
            *sixteen(wrong=("q03",)),
        ],
    ),
    run(
        "2026-10-03_02_preprod-c1",
        environment="preprod",
        question_set="v6",
        config={
            "url": "https://preprod.example",
            "server": {"chat_model": "alias", "collection": "c1", "version": "abc1234"},
        },
        results=sixteen(),
    ),
    run(
        "2026-10-04_01_preprod-c2",
        environment="preprod",
        question_set="v6",
        milestone=True,
        config={"server": {"chat_model": "alias", "collection": "c2"}},
        results=[
            line(
                "q01",
                "partial",
                review_note="Il manque la remise",
                auto_check={"verdict": "correct"},
            ),
            line("q02", auto_check={"verdict": "correct"}),
        ],
    ),
    run(
        "2026-10-04_02_retrieval",
        kind="retrieval",
        milestone=True,
        config={"grade_threshold": 0.47, "embedding_model": "org/MiniLM"},
        results=[
            {"question_id": "q01", "passed": True, "rank": 2, "top_score": 0.6},
            {"question_id": "q02", "passed": False, "top_score": 0.49},
            {
                "question_id": "q17",
                "passed": True,
                "out_of_scope": "threshold",
                "refused_by_threshold": True,
                "top_score": 0.46,
            },
        ],
    ),
    run(
        "2026-10-04_03_conversations",
        kind="conversation",
        question_set="c2",
        milestone=True,
        results=[line("c01.1", conversation="c01", turn=1)],
    ),
]


@pytest.fixture
def results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for item in RUNS:
        path = tmp_path / f"{item['run_id']}.json"
        path.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "2026-10-05_01_broken.json").write_text("{", encoding="utf-8")
    # A result line without `passed` (the format of eval/results.py requires it)
    odd = run("2026-10-05_03_odd", results=[{"question_id": "q01", "verdict": "correct"}])
    (tmp_path / "2026-10-05_03_odd.json").write_text(json.dumps(odd), encoding="utf-8")
    future = run("2026-10-05_02_future", schema_version=results.SCHEMA_VERSION + 1)
    (tmp_path / "2026-10-05_02_future.json").write_text(json.dumps(future), encoding="utf-8")
    monkeypatch.setattr(results, "RESULTS_DIR", tmp_path)
    return tmp_path


def by_id(loaded: dashboard.Loaded) -> dict[str, dict]:
    return {item["run_id"]: item for item in loaded.runs}


class TestLoading:
    def test_unreadable_files_are_left_out_and_listed(self, results_dir: Path):
        loaded = dashboard.load_runs()
        assert [item["run_id"] for item in loaded.runs] == [item["run_id"] for item in RUNS]
        reasons = dict(loaded.skipped)
        assert reasons["2026-10-05_01_broken.json"] == "JSON illisible"
        assert "version de format" in reasons["2026-10-05_02_future.json"]
        assert reasons["2026-10-05_03_odd.json"] == "résultats illisibles"

    def test_runs_are_kept_until_a_file_changes(self, results_dir: Path):
        first = dashboard.load_runs()
        assert dashboard.load_runs() is first
        path = results_dir / "2026-10-02_01_local-a.json"
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        assert dashboard.load_runs() is not first

    def test_load_says_what_could_not_be_read(self, results_dir: Path):
        data = dashboard.load()
        assert len(data.runs) == len(RUNS)
        assert any("broken" in problem for problem in data.problems)
        assert data.questions and data.edge_cases  # the real catalogs of eval/

    def test_an_empty_folder_gives_no_run(self, tmp_path: Path):
        loaded = dashboard.load_runs(tmp_path / "missing")
        assert loaded.runs == [] and loaded.skipped == []


class TestOneRun:
    def test_configuration_of_a_local_run(self, results_dir: Path):
        item = by_id(dashboard.load_runs())["2026-10-02_01_local-a"]
        assert dashboard.model(item) == "model-a"
        assert dashboard.threshold(item) == 0.45
        assert dashboard.collection(item) is None
        assert dashboard.version(item) == "1234abc"  # the commit of the machine

    def test_configuration_of_a_server_run_comes_from_its_health(self, results_dir: Path):
        item = by_id(dashboard.load_runs())["2026-10-03_02_preprod-c1"]
        assert dashboard.model(item) == "alias"
        assert dashboard.collection(item) == "c1"
        assert dashboard.version(item) == "abc1234"  # not the commit of the runner

    def test_a_reconstructed_value_says_so(self):
        item = run(
            "2026-10-06_07_preprod",
            environment="preprod",
            config={
                "llm_model": "alias",
                "llm_model_source": "reconstitué",
                "server_version": "434b043",
            },
        )
        assert dashboard.model(item) == "alias"
        assert dashboard.reconstructed(item, "llm_model")
        assert dashboard.version(item) == "434b043"
        assert not dashboard.reconstructed(item, "server_version")

    def test_an_older_server_run_is_unknown(self, results_dir: Path):
        item = by_id(dashboard.load_runs())["2026-10-01_01_prod-six"]
        assert dashboard.model(item) is None
        assert dashboard.version(item) is None

    def test_quality_comes_from_the_reviewed_verdicts(self, results_dir: Path):
        runs = by_id(dashboard.load_runs())
        quality = dashboard.quality(runs["2026-10-02_01_local-a"])
        # 16 right + q99 partial: the stale summary (15) is not used
        assert (quality.in_scope_ok, quality.in_scope_total) == (16, 17)
        assert (quality.out_of_scope_ok, quality.out_of_scope_total) == (1, 1)
        assert quality.reference_ok == 16
        assert dashboard.quality(runs["2026-10-03_01_local-b"]).reference_ok == 15
        assert dashboard.quality(runs["2026-10-03_01_local-b"]).wrong == 1

    def test_no_reference_score_without_the_sixteen_questions(self, results_dir: Path):
        item = by_id(dashboard.load_runs())["2026-10-01_01_prod-six"]
        quality = dashboard.quality(item)
        assert quality.reference_ok is None
        assert (quality.in_scope_ok, quality.in_scope_total, quality.out_of_scope_total) == (
            6,
            6,
            0,
        )

    def test_retrieval_quality_and_margins(self, results_dir: Path):
        item = by_id(dashboard.load_runs())["2026-10-04_02_retrieval"]
        quality = dashboard.quality(item)
        assert (quality.in_scope_ok, quality.in_scope_total) == (1, 2)
        assert (quality.out_of_scope_ok, quality.out_of_scope_total) == (1, 1)
        found = dashboard.margins(item)
        assert found is not None
        assert (found.in_scope_min, found.out_of_scope_max, found.threshold) == (0.49, 0.46, 0.47)
        assert round(found.gap, 3) == 0.03

    def test_mark_is_the_cell_of_the_report(self, results_dir: Path):
        item = by_id(dashboard.load_runs())["2026-10-04_02_retrieval"]
        assert dashboard.mark(item, item["results"][0]) == "✅ 2"
        # Refused by the threshold, as an out-of-scope question should: no rank to show
        assert dashboard.mark(item, item["results"][2]) == "✅ ⛔"
        assert dashboard.mark(item, None) == "·"


def test_select_and_latest(results_dir: Path):
    runs = dashboard.load_runs().runs
    assert [r["run_id"] for r in dashboard.select(runs, "e2e", "preprod")] == [
        "2026-10-03_02_preprod-c1",
        "2026-10-04_01_preprod-c2",
    ]
    milestones = dashboard.select(runs, "e2e", milestones_only=True)
    assert [r["run_id"] for r in milestones] == [
        "2026-10-02_01_local-a",
        "2026-10-04_01_preprod-c2",
    ]
    latest = dashboard.latest(runs, "e2e", "local")
    assert latest is not None and latest["run_id"] == "2026-10-03_01_local-b"
    assert dashboard.latest(runs, "e2e", "nowhere") is None


def test_changes_between_runs_of_the_same_environment(results_dir: Path):
    found = dashboard.changes(dashboard.load_runs().runs)
    assert found["2026-10-03_01_local-b"] == [
        "jeu v5 → v6",
        "modèle model-a → model-b",
        "seuil 0,45 → 0,47",
    ]
    assert found["2026-10-04_01_preprod-c2"] == ["collection c1 → c2"]
    # The first run of an environment, or one that records nothing new, changes nothing
    assert "2026-10-03_02_preprod-c1" not in found
    assert "2026-10-01_01_prod-six" not in found


def test_matrix_rows_and_cells(results_dir: Path):
    runs = dashboard.select(dashboard.load_runs().runs, "e2e", milestones_only=True)
    rows = dashboard.matrix(runs, QUESTIONS, CASES)
    ids = [row.question_id for row in rows]
    # Ynov questions, then out of scope, then the questions no longer in the set
    assert ids[:16] == [f"q{n:02d}" for n in range(1, 17)]
    assert ids[16:] == ["q17", "q99"]
    assert rows[16].out_of_scope and not rows[17].out_of_scope
    assert rows[17].question == "Une question retirée du jeu ?"
    q01 = rows[0]
    assert [cell.state for cell in q01.cells] == ["correct", "partial"]
    assert q01.cells[1].tip == "partielle — Il manque la remise"
    assert rows[2].cells[1] == dashboard.Cell("absent", "·", "question absente de ce passage")
    assert rows[1].edge_cases == ["EC-01", "EC-02"]


def test_conversation_runs_stay_out_of_the_matrix(results_dir: Path):
    runs = dashboard.load_runs().runs
    for kind in ("e2e", "retrieval"):
        rows = dashboard.matrix(dashboard.select(runs, kind), QUESTIONS, CASES)
        assert "c01.1" not in [row.question_id for row in rows]


def test_edge_case_counts_follow_the_order_of_the_statuses():
    counts = dashboard.edge_case_counts([*CASES, {"id": "EC-09", "status": "weird"}])
    assert list(counts) == [*dashboard.STATUS_LABELS, "weird"]
    assert (counts["open"], counts["fixed"], counts["lesson"], counts["weird"]) == (1, 1, 1, 1)


def test_auto_check_agreement(results_dir: Path):
    found = dashboard.auto_check_agreement(dashboard.load_runs().runs)
    assert (found.agree, found.reviewed) == (1, 2)
    assert found.disagreements == [("2026-10-04_01_preprod-c2", "q01", "partial", "correct")]


def test_the_report_uses_the_reviewed_verdicts(results_dir: Path):
    md = report.build()
    # local-a: 16 right out of 17 Ynov questions, not the 15 of its stale summary
    assert "| `2026-10-02_01_local-a` | e2e | local | v5 | modèle model-a | 16/17 ✅" in md
    assert "concorde dans 1/2 cas" in md
    assert "`2026-10-04_01_preprod-c2` q01 : revue **partial**, automatique **correct**" in md


# --- Charts -------------------------------------------------------------------------------------


def test_line_chart_draws_every_series_with_its_marker():
    svg = charts.line_chart(
        ["a", "b", "c"],
        [
            charts.Series("Local", [charts.Point(1), charts.Point(2), charts.Point(3)]),
            charts.Series(
                "Préprod",
                [charts.Point(None), charts.Point(2, hollow=True), charts.Point(1, highlight=True)],
                marker="diamond",
                tone=1,
            ),
            charts.Series("Seuil", [charts.Point(1.5)] * 3, marker="none", dashed=True, tone=3),
        ],
        title="Un graphique",
        y_max=4,
    )
    drawing, legend = svg.split("</svg>", 1)
    assert drawing.count("<circle") == 3  # the points of « Local »
    assert drawing.count("<polygon") == 2  # the diamonds of « Préprod », none at its gap
    # Legend: a swatch per series, then what highlighted and hollow points mean
    assert legend.count("<li>") == 5
    assert 'class="pt hollow"' in svg and 'class="pt hl"' in svg
    assert 'class="line dashed"' in svg
    assert 'role="img" aria-label="Un graphique"' in svg
    assert "étape clé" in svg and "peu de cas" in svg
    assert "<script" not in svg


def test_line_chart_escapes_every_text():
    evil = "<script>alert(1)</script>"
    svg = charts.line_chart(
        [evil],
        [charts.Series(evil, [charts.Point(1, tip=evil)])],
        title=evil,
        y_max=2,
        y_format=lambda _value: evil,
        rules=[charts.Rule(1, evil)],
        marks=[charts.Mark(0, evil, evil)],
    )
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_a_gap_breaks_the_line_unless_connected():
    def path(connect: bool) -> str:
        svg = charts.line_chart(
            ["a", "b", "c"],
            [
                charts.Series(
                    "S",
                    [charts.Point(1), charts.Point(None), charts.Point(2)],
                    connect_gaps=connect,
                )
            ],
            title="t",
            y_max=2,
        )
        return svg.split('class="line" d="')[1].split('"')[0]

    assert path(True).count("M") == 1
    assert path(False).count("M") == 2


def test_rules_and_marks_are_drawn_with_their_tooltip():
    svg = charts.line_chart(
        ["a", "b"],
        [charts.Series("S", [charts.Point(1), charts.Point(2)])],
        title="t",
        y_max=2,
        rules=[charts.Rule(1.5, "Seuil 1,5")],
        marks=[charts.Mark(1, "1", "modèle a → b"), charts.Mark(5, "2", "hors du graphique")],
    )
    assert 'class="rule"' in svg and "Seuil 1,5" in svg
    assert svg.count('<g class="mark">') == 1
    assert "<title>modèle a → b</title>" in svg


def test_data_table_escapes_and_aligns_numbers():
    html = charts.data_table(
        ["Nom", "Nombre"], [["<b>x</b>", "3"]], summary="Les <données>", numeric=(1,)
    )
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert '<td class="num">3</td>' in html
    assert "<summary>Les &lt;données&gt;</summary>" in html
    assert "<details" in html
