"""Report and exit status of eval.e2e used by the production workflow."""

from eval import e2e


def _result(qid: str, verdict: str) -> dict:
    return {"question_id": qid, "question": f"Question {qid} ?", "verdict": verdict}


def test_summary_counts_and_lists_what_is_not_correct() -> None:
    summary = e2e.markdown_summary(
        [_result("q01", "correct"), _result("q02", "partial"), _result("q03", "error")], "titre"
    )
    assert "1/3 réponses correctes" in summary
    assert "| partial | 1 |" in summary and "| error | 1 |" in summary
    assert "q02 Question q02 ?" in summary and "q01 Question" not in summary


def test_summary_of_a_clean_run_has_no_detail_table() -> None:
    summary = e2e.markdown_summary([_result("q01", "correct")], "titre")
    assert "1/1 réponses correctes" in summary
    assert "| Question |" not in summary
