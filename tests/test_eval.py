"""Tests for the evaluation reporting (answer checks, run files, report)."""
import json
from pathlib import Path

import pytest

from eval import report, results

QUESTION = {"id": "q03", "question": "Le Mastère Game Programmer est-il proposé à Lyon ?",
            "answer_must": ["en ligne"], "answer_must_not": [r"^\W*oui\b"]}


class TestCheckAnswer:
    def test_correct(self):
        check = results.check_answer(QUESTION, "Non, il est **100 % en ligne**.")
        assert check["verdict"] == "correct"

    def test_forbidden_pattern_makes_it_wrong(self):
        check = results.check_answer(QUESTION, "Oui, à Lyon, et aussi en ligne.")
        assert check["verdict"] == "wrong"
        assert check["must_not_hits"] == [r"^\W*oui\b"]

    def test_partial_when_some_facts_missing(self):
        q = {"answer_must": ["9[  ]?000", "9[  ]?500"]}
        assert results.check_answer(q, "9 000 € au comptant")["verdict"] == "partial"

    def test_no_answer(self):
        answer = "Le contexte fourni ne mentionne pas explicitement cette information."
        assert results.check_answer(QUESTION, answer)["verdict"] == "no_answer"

    def test_refused(self):
        assert results.check_answer(QUESTION, "…", refused=True)["verdict"] == "refused"


@pytest.fixture
def results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(results, "RESULTS_DIR", tmp_path)
    return tmp_path


def test_save_run_adds_schema_and_summary(results_dir: Path):
    run_id = results.next_run_id("2026-10-03", "Mon test !")
    assert run_id == "2026-10-03_01_mon-test"
    path = results.save_run({
        "run_id": run_id, "date": "2026-10-03", "kind": "e2e", "environment": "prod",
        "question_set": "v4", "label": "x",
        "results": [{"question_id": "q01", "passed": True, "verdict": "correct"},
                    {"question_id": "q13", "passed": False, "verdict": "refused"}],
    })
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == results.SCHEMA_VERSION
    assert saved["summary"]["correct"] == 1 and saved["summary"]["refused"] == 1
    assert results.next_run_id("2026-10-03", "suivant") == "2026-10-03_02_suivant"


def test_report_builds_from_runs(results_dir: Path):
    results.save_run({
        "run_id": "2026-10-03_01_ret", "date": "2026-10-03", "kind": "retrieval",
        "environment": "local", "question_set": "v4", "label": "ret", "milestone": True,
        "config": {"chunk_size": 300, "limit": 10, "candidates": 40, "max_per_section": 2},
        "results": [{"question_id": "q13", "passed": True, "rank": 2, "min_distinct": 1,
                     "distinct_sections": 1, "refused_by_threshold": True}],
    })
    md = report.build()
    assert "`2026-10-03_01_ret`" in md
    assert "✅ 2 ⛔" in md  # q13 retrieved at rank 2 but refused by the threshold
    assert "### EC-02" in md  # edge cases catalog is included
