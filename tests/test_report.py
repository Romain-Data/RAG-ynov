"""Tests for the monthly report of the questions left without an answer (#20, no LLM)."""

import sys
from datetime import UTC, datetime

import pytest

from chat.db import db
from journal import report, store, themes

REFUSED = {"grade": "refuse", "retrieved": [], "sources": [], "llm_model": None}
SEARCHED = [{"source": "bts-sio.html", "section": "Tarifs", "score": 0.7}]
ANSWERED = {
    "grade": "ok",
    "answer": "Le BTS SIO coûte 7 000 € par an [Source 1].",
    "retrieved": SEARCHED,
    "sources": [],
}
INCOMPLETE = {
    **ANSWERED,
    "answer": (
        "Le BTS SIO coûte 7 000 € par an [Source 1]. Le contexte ne précise pas le tarif de "
        "l'année prochaine."
    ),
}
GREETING = {"grade": "ok", "answer": "Bonjour !", "retrieved": [], "sources": []}


def entry(
    question: str,
    when: str,
    *,
    result: dict = REFUSED,
    theme: str = "",
    thread: str | None = "t1",
    feedback: int | None = None,
    error: str | None = None,
) -> int:
    """An entry of the journal asked at `when` (ISO), put in `theme` when given."""
    store.record(
        channel="chat" if thread else "api",
        question=question,
        result=None if error else result,
        error=error,
        thread_id=thread,
    )
    with db() as conn:
        entry_id = int(conn.execute("SELECT MAX(id) FROM answer_log").fetchone()[0])
        conn.execute(
            "UPDATE answer_log SET created_at = ?, feedback = ? WHERE id = ?",
            (when, feedback, entry_id),
        )
    if theme:
        assert themes.move(entry_id, new_name=theme) is None
    return entry_id


def theme_named(name: str) -> int:
    return next(t["id"] for t in themes.choices() if t["name"] == name)


class TestMonths:
    @pytest.mark.parametrize(
        ("raw", "month"),
        [("2026-10", "2026-10"), (" 2026-01 ", "2026-01"), ("2026-12", "2026-12")],
    )
    def test_a_valid_month(self, raw, month):
        assert report.parse_month(raw) == month

    @pytest.mark.parametrize(
        "raw", ["", None, "2026-13", "2026-00", "2026-1", "26-10", "1999-12", "../2026-10", "x"]
    )
    def test_anything_else_is_the_current_month(self, raw):
        assert report.parse_month(raw) == datetime.now(UTC).strftime("%Y-%m")

    def test_previous_month_and_bounds(self):
        assert report.previous_month("2026-10") == "2026-09"
        assert report.previous_month("2026-01") == "2025-12"
        assert report.bounds("2026-12") == ("2026-12-01", "2027-01-01")
        assert report.bounds("2026-02") == ("2026-02-01", "2026-03-01")

    def test_labels_in_french(self):
        assert report.month_label("2026-08") == "août 2026"
        assert report.month_label("2027-02") == "février 2027"

    @pytest.mark.parametrize(
        ("now", "before", "trend"),
        [(3, 0, "nouveau"), (3, 1, "en hausse"), (2, 2, "stable"), (1, 4, "en baisse")],
    )
    def test_trend(self, now, before, trend):
        assert report.trend(now, before) == trend

    def test_available_months(self):
        entry("Une question ?", "2026-08-15T10:00:00+00:00")
        entry("Une autre ?", "2026-08-20T10:00:00+00:00")
        entry("Encore une ?", "2026-06-02T10:00:00+00:00")
        found = report.available_months("2025-01")
        current = datetime.now(UTC).strftime("%Y-%m")
        assert found == sorted({current, "2026-08", "2026-06", "2025-01"}, reverse=True)


class TestMonthReport:
    def test_an_empty_month(self):
        data = report.month_report("2026-10")
        assert data["counts"]["questions"] == 0 and data["unthemed"] == 0
        assert data["missing"] == data["to_check"] == data["search"] == data["off_topic"] == []
        assert data["label"] == "octobre 2026" and data["previous_label"] == "septembre 2026"

    def test_counts_leave_greetings_and_errors_out(self):
        october = "2026-10-10T10:00:00+00:00"
        entry("Un logement ?", october)
        entry("Le prix du BTS SIO ?", october, result=ANSWERED)
        entry("Le prix l'an prochain ?", october, result=INCOMPLETE)
        entry("Le BTS SIO en alternance ?", october, result=ANSWERED, feedback=0)
        entry("Bonjour", october, result=GREETING)
        entry("Les tarifs ?", october, error="LLMUnavailableError: 429")
        counts = report.month_report("2026-10")["counts"]
        assert counts["questions"] == 4  # the greeting and the error are not questions here
        assert counts["without_answer"] == 1
        assert counts["by_kind"]["incomplete"] == 1 and counts["by_kind"]["pas_utile"] == 1

    def test_the_month_is_bounded_in_utc(self):
        entry("Premier jour ?", "2026-10-01T00:00:00+00:00")
        entry("Dernier jour ?", "2026-10-31T23:59:59.999999+00:00")
        entry("Lendemain ?", "2026-11-01T00:00:00+00:00")
        entry("Veille ?", "2026-09-30T23:59:59+00:00")
        assert report.month_report("2026-10")["counts"]["questions"] == 2
        assert report.month_report("2026-10")["previous_counts"]["questions"] == 1

    def test_comparison_with_the_month_before(self):
        entry("Un logement ?", "2026-09-10T10:00:00+00:00", theme="Logement étudiant")
        for number in range(3):
            entry(
                f"Une chambre {number} ?",
                "2026-10-10T10:00:00+00:00",
                theme="Logement étudiant",
                thread=f"t{number}",
            )
        entry("La rentrée ?", "2026-10-11T10:00:00+00:00", theme="Date de rentrée")
        data = report.month_report("2026-10")
        found = {t["name"]: t for t in data["to_check"]}
        assert found["Logement étudiant"]["trend"] == "en hausse"
        assert found["Logement étudiant"]["previous"] == 1
        assert found["Date de rentrée"]["trend"] == "nouveau"
        assert data["previous_counts"]["questions"] == 1

    def test_themes_go_to_the_section_of_their_cause(self):
        when = "2026-10-10T10:00:00+00:00"
        entry("Un logement ?", when, theme="Logement étudiant")
        entry("La rentrée ?", when, theme="Date de rentrée")
        entry("Le prix du BTS SIO ?", when, theme="Frais de scolarité")
        entry("Quel temps fait-il ?", when, theme="Hors sujet")  # a fixed theme: off topic
        themes.set_cause(theme_named("Logement étudiant"), "contenu", "Pas de page logement.")
        themes.set_cause(theme_named("Frais de scolarité"), "recherche", "Repris en q35.")
        data = report.month_report("2026-10")
        assert [t["name"] for t in data["missing"]] == ["Logement étudiant"]
        assert data["missing"][0]["note"] == "Pas de page logement."
        assert [t["name"] for t in data["to_check"]] == ["Date de rentrée"]
        assert [t["name"] for t in data["search"]] == ["Frais de scolarité"]
        assert [t["name"] for t in data["off_topic"]] == ["Hors sujet"]
        assert data["off_topic_total"] == 1

    def test_only_the_main_off_topic_themes_are_listed(self):
        when = "2026-10-10T10:00:00+00:00"
        for number in range(report.OFF_TOPIC_SHOWN + 2):
            entry(f"Hors sujet {number} ?", when, theme=f"Sujet {number}")
            themes.set_cause(theme_named(f"Sujet {number}"), "hors_sujet")
        data = report.month_report("2026-10")
        assert len(data["off_topic"]) == report.OFF_TOPIC_SHOWN
        assert data["off_topic_total"] == report.OFF_TOPIC_SHOWN + 2

    def test_examples_need_two_conversations(self):
        when = "2026-10-10T10:00:00+00:00"
        # one visitor asking three times: one conversation, nothing quoted
        for _ in range(3):
            entry("Ynov a des logements ?", when, theme="Logement étudiant", thread="same")
        data = report.month_report("2026-10")
        housing = data["to_check"][0]
        assert housing["questions"] == 3 and housing["conversations"] == 1
        assert not housing["quoted"] and housing["examples"] == []

    def test_examples_the_most_asked_first(self):
        when = "2026-10-10T10:00:00+00:00"
        entry("Une chambre à Lyon ?", when, theme="Logement étudiant", thread="a")
        entry("Ynov a des logements ?", when, theme="Logement étudiant", thread="b")
        entry("ynov a des LOGEMENTS", when, theme="Logement étudiant", thread="c")
        entry("Une résidence ?", when, theme="Logement étudiant", thread=None)  # the API
        housing = report.month_report("2026-10")["to_check"][0]
        assert housing["conversations"] == 4 and housing["quoted"]
        # the question asked twice (case and punctuation aside) first, then the latest one
        assert housing["examples"] == ["ynov a des LOGEMENTS", "Une résidence ?"]

    def test_questions_not_grouped_yet(self):
        entry("Pas rangée ?", "2026-10-10T10:00:00+00:00")
        entry("Rangée ?", "2026-10-10T10:00:00+00:00", theme="Logement étudiant")
        entry("Pas rangée non plus ?", "2026-09-10T10:00:00+00:00")
        assert report.month_report("2026-10")["unthemed"] == 1


class TestCommand:
    def test_writes_the_file_of_a_month(self, tmp_path, monkeypatch):
        entry("Un logement ?", "2026-10-10T10:00:00+00:00", theme="Logement étudiant")
        out = tmp_path / "rapport.html"
        monkeypatch.setattr(sys, "argv", ["report", "--mois", "2026-10", "--out", str(out)])
        report.main()
        html = out.read_text(encoding="utf-8")
        assert "Questions sans réponse : octobre 2026" in html
        assert "Logement étudiant" in html and "/admin" not in html
