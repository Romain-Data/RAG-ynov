"""The regression check of eval.retrieval, used by the CI."""

import json
from pathlib import Path

from eval import retrieval

CONFIG = {"embedding_model": "m", "chunk_size": 300}


def _results(**passed: bool) -> list[dict]:
    return [{"question_id": qid, "passed": ok} for qid, ok in passed.items()]


def _baseline(**passed: bool) -> dict:
    return retrieval.make_baseline(_results(**passed), CONFIG)


def test_same_results_are_no_regression() -> None:
    results = _results(q01=True, q02=False)
    assert retrieval.regressions(results, _baseline(q01=True, q02=False), CONFIG) == []


def test_a_question_that_passed_and_fails_is_a_regression() -> None:
    problems = retrieval.regressions(_results(q01=False), _baseline(q01=True), CONFIG)
    assert problems == ["q01: passed in the baseline, fails now"]


def test_a_question_fixed_is_not_a_regression() -> None:
    assert retrieval.regressions(_results(q01=True), _baseline(q01=False), CONFIG) == []


def test_a_changed_question_set_must_rewrite_the_baseline() -> None:
    results = _results(q01=True, q02=True)
    problems = retrieval.regressions(results, _baseline(q01=True), CONFIG)
    assert problems == ["q02: not in the baseline"]
    problems = retrieval.regressions(_results(q01=True), _baseline(q01=True, q02=True), CONFIG)
    assert problems == ["q02: in the baseline, not in the run"]


def test_a_changed_setting_is_reported() -> None:
    other = {**CONFIG, "chunk_size": 500}
    problems = retrieval.regressions(_results(q01=True), _baseline(q01=True), other)
    assert len(problems) == 1 and "settings" in problems[0]


def test_the_committed_baseline_covers_the_current_questions() -> None:
    """Adding a question without rewriting eval/ci_baseline.json would break the CI."""
    baseline = json.loads(Path("eval/ci_baseline.json").read_text())
    expected = {q["id"] for q in retrieval.load_questions() if q.get("out_of_scope") != "llm"}
    assert set(baseline["passed"]) == expected
    assert baseline["question_set"] == retrieval.QUESTION_SET
