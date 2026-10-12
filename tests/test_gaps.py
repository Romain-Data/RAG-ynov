"""Tests for the detection of the questions left without an answer (#20, journal/gaps.py)."""

from pathlib import Path

import pytest
import yaml

from chat.db import db
from journal import gaps, review, stats, store

FIXTURE = Path(__file__).parent / "fixtures" / "gap_answers.yaml"
ANSWERS = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))

REFUSED = {"grade": "refuse", "retrieved": [], "sources": [], "answer": "Je n'ai pas trouvé…"}
RETRIEVED = [{"source": "bts-sio.html", "section": "Tarifs", "page": None, "score": 0.71}]
ANSWERED = "Le BTS SIO coûte 7 400 € par an [Source 1]."
DOES_NOT_KNOW = "Le contexte ne précise pas quels BTS sont accessibles via Parcoursup."


@pytest.mark.parametrize("item", ANSWERS, ids=[item["id"] for item in ANSWERS])
def test_the_real_answers_of_the_llm(item):
    """Every answer saved in eval/results/ that the fixture holds gets the label it was given
    by hand: the detector is tuned on what the LLM actually writes."""
    assert gaps.answer_gap(item["answer"]) == item["kind"]


def test_the_fixture_covers_every_kind_of_answer():
    kinds = {item["kind"] for item in ANSWERS}
    assert kinds == {"aveu", "hors_ynov", "incomplete", None}
    assert all(item["answer"].strip() for item in ANSWERS)


class TestAnswerGap:
    def test_typographic_apostrophes(self):
        assert gaps.answer_gap("Je ne peux répondre qu’aux questions sur Ynov Campus.") == (
            "hors_ynov"
        )
        assert gaps.answer_gap("Je n’ai pas d’information sur ce point.") == "aveu"

    def test_markdown_and_source_marks_are_ignored(self):
        assert gaps.answer_gap("**Le contexte ne précise pas** ce point. [Sources 1–10]") == "aveu"

    def test_a_gap_next_to_facts_is_incomplete(self):
        answer = f"{ANSWERED} Le contexte ne précise pas les dates de rentrée."
        assert gaps.answer_gap(answer) == "incomplete"

    def test_asides_are_neither_facts_nor_gaps(self):
        answer = f"{DOES_NOT_KNOW} Pour obtenir cette information, il faudrait contacter l'école."
        assert gaps.answer_gap(answer) == "aveu"

    def test_rule_5_wins_over_an_admission(self):
        answer = "Je ne dispose d'aucune information. Je ne réponds qu'aux questions sur Ynov."
        assert gaps.answer_gap(answer) == "hors_ynov"

    @pytest.mark.parametrize(
        "answer",
        [
            ANSWERED,
            "Non, le Mastère est 100 % en ligne et n'est proposé sur aucun campus.",
            "Ce module n'est pas spécifique au Mastère 2.",
            "Le statut étudiant n'est pas disponible sur Ynov Connect.",
            "",
        ],
    )
    def test_answers_that_report_nothing_missing(self, answer):
        assert gaps.answer_gap(answer) is None


class TestGapKind:
    def test_a_refusal_at_the_threshold(self):
        assert gaps.gap_kind("refuse", "Je n'ai pas trouvé…", None) == "refus"
        assert gaps.gap_kind("refuse", "Je n'ai pas trouvé…", 0) == "refus"  # refus first

    def test_greetings_and_errors_have_no_kind(self):
        for route in ("smalltalk", "error", None):
            assert gaps.gap_kind(route, DOES_NOT_KNOW, 0) is None

    def test_a_generated_answer(self):
        assert gaps.gap_kind("generate", ANSWERED, None) is None
        assert gaps.gap_kind("generate", ANSWERED, 1) is None
        assert gaps.gap_kind("generate", DOES_NOT_KNOW, None) == "aveu"

    def test_the_wording_comes_before_the_thumb(self):
        assert gaps.gap_kind("generate", DOES_NOT_KNOW, 0) == "aveu"
        assert gaps.gap_kind("generate", ANSWERED, 0) == "pas_utile"

    def test_a_missing_answer(self):
        assert gaps.gap_kind("generate", None, None) is None

    def test_the_kinds_and_their_order(self):
        assert list(gaps.GAP_KINDS) == ["refus", "hors_ynov", "aveu", "incomplete", "pas_utile"]
        assert set(gaps.WITHOUT_ANSWER) < set(gaps.GAP_KINDS)


def add(question: str, answer: str = ANSWERED, **kwargs) -> int:
    result = {"answer": answer, "grade": "ok", "sources": [], "retrieved": RETRIEVED}
    result.update(kwargs.pop("result", {}))
    if "rewritten" in kwargs:
        result["rewritten"] = kwargs.pop("rewritten")
    store.record(channel=kwargs.pop("channel", "chat"), question=question, result=result, **kwargs)
    with db() as conn:
        return int(conn.execute("SELECT MAX(id) FROM answer_log").fetchone()[0])


def rate(entry_id: int, value: int) -> None:
    with db() as conn:
        conn.execute("UPDATE answer_log SET feedback = ? WHERE id = ?", (value, entry_id))


def fill() -> dict[str, int]:
    ids = {
        "answered": add("Prix du BTS SIO ?"),
        "refused": add("Quel temps à Lyon ?", result=REFUSED),
        "other_school": add("Prix de HEC ?", "Je ne peux répondre qu'aux questions sur Ynov."),
        "unknown": add("Le BTS est-il sur Parcoursup ?", DOES_NOT_KNOW),
        "partial": add("Prix et rentrée ?", f"{ANSWERED} Le contexte ne précise pas la rentrée."),
        "not_useful": add("Prix du BTS MEC ?"),
        "hello": add("Bonjour", "Bonjour !", result={"retrieved": []}),
    }
    rate(ids["not_useful"], 0)
    rate(ids["hello"], 0)  # a greeting is never a question left without an answer
    store.record(channel="api", question="Q ?", error="LLMUnavailableError: 429")
    return ids


class TestInTheDatabase:
    def test_every_connection_knows_the_function(self):
        ids = fill()
        with db() as conn:
            found = dict(
                conn.execute("SELECT id, gap_kind(route, answer, feedback) FROM answer_log")
            )
        assert found[ids["answered"]] is None
        assert found[ids["refused"]] == "refus"
        assert found[ids["other_school"]] == "hors_ynov"
        assert found[ids["unknown"]] == "aveu"
        assert found[ids["partial"]] == "incomplete"
        assert found[ids["not_useful"]] == "pas_utile"
        assert found[ids["hello"]] is None
        assert sum(kind is None for kind in found.values()) == 3  # answered, hello, the error

    def test_a_follow_up_is_judged_on_its_answer(self):
        entry_id = add("Et à Lyon ?", DOES_NOT_KNOW, rewritten="Le BTS SIO est-il à Lyon ?")
        entry = review.get_entry(entry_id)
        assert entry["gap"] == "aveu" and entry["question"] == "Et à Lyon ?"

    def test_the_list_filter(self):
        ids = fill()

        def listed(gap: str | None) -> set[int]:
            return {row["id"] for row in review.list_entries(gap=gap)[0]}

        everything = listed(None)
        assert listed("tous") == {
            ids[name] for name in ("refused", "other_school", "unknown", "partial", "not_useful")
        }
        assert listed("aucune") == {ids["refused"], ids["other_school"], ids["unknown"]}
        assert listed("incomplete") == {ids["partial"]}
        assert listed("pas_utile") == {ids["not_useful"]}
        assert listed("nimporte") == everything  # unknown: no filter, like the thumbs
        rows, _ = review.list_entries(gap="aveu")
        assert [row["gap"] for row in rows] == ["aveu"]

    def test_the_summary_counts_out_of_the_questions_that_reached_the_search(self):
        fill()
        found = stats.summary()["gaps"]
        assert found["questions"] == 6  # without the greeting and the error
        assert found["by_kind"] == {
            "refus": 1,
            "hors_ynov": 1,
            "aveu": 1,
            "incomplete": 1,
            "pas_utile": 1,
        }
        assert found["without_answer"] == 3 and found["flagged"] == 5

    def test_an_empty_journal(self):
        found = stats.summary("7")["gaps"]
        assert found["questions"] == 0 and found["flagged"] == 0
        assert set(found["by_kind"].values()) == {0}
