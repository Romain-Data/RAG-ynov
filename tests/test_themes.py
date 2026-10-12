"""Tests for the themes of the questions left without an answer (#20): the grouping by the LLM
(simulated: real answers recorded at the calibration are replayed), the reads of the /admin
pages, the decisions about a theme and the migration of an older database. No LLM call."""

import logging
import sqlite3
from pathlib import Path

import pytest
import yaml

from app.core.config import settings
from chat.db import SCHEMA, db, init_db
from graph.llm import LLMUnavailableError
from journal import store, themes

FIXTURES = Path(__file__).parent / "fixtures"
RUNS = yaml.safe_load((FIXTURES / "gap_grouping_runs.yaml").read_text(encoding="utf-8"))
QUESTIONS = yaml.safe_load((FIXTURES / "gap_questions.yaml").read_text(encoding="utf-8"))
REFUSED = {"grade": "refuse", "retrieved": [], "sources": []}
DOES_NOT_KNOW = "Le contexte ne précise pas quels BTS sont accessibles via Parcoursup."
ANSWERED = {
    "grade": "ok",
    "answer": "Environ 7 000 € par an [Source 1].",
    "retrieved": [{"source": "a.html", "section": "Tarifs", "score": 0.7}],
    "sources": [],
}


def refused(question: str, **kwargs) -> int:
    """An entry refused at the threshold (kind "refus"), and its id."""
    store.record(channel=kwargs.pop("channel", "chat"), question=question, result=REFUSED, **kwargs)
    return last_id()


def last_id() -> int:
    with db() as conn:
        return int(conn.execute("SELECT MAX(id) FROM answer_log").fetchone()[0])


def theme_of(entry_id: int) -> str | None:
    with db() as conn:
        row = conn.execute(
            "SELECT t.name FROM answer_log a LEFT JOIN gap_theme t ON t.id = a.gap_theme_id "
            "WHERE a.id = ?",
            (entry_id,),
        ).fetchone()
    return row[0]


def theme_id_of(entry_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT gap_theme_id FROM answer_log WHERE id = ?", (entry_id,))
        return int(row.fetchone()[0])


def theme_rows() -> dict[str, str | None]:
    with db() as conn:
        return dict(conn.execute("SELECT name, cause FROM gap_theme").fetchall())


class FakeLLM:
    """Stands for graph.llm.chat_completion: answers in turn, records each payload."""

    def __init__(self, *answers: str | Exception, finish: list[str] | None = None) -> None:
        self.answers = list(answers)
        self.finish = list(finish or [])
        self.payloads: list[dict] = []
        self.timeouts: list[float] = []

    def __call__(self, payload: dict, timeout: float = 30.0) -> dict:
        self.payloads.append(payload)
        self.timeouts.append(timeout)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return {
            "model": "mammouth-recommended",
            "choices": [
                {
                    "message": {"content": answer},
                    "finish_reason": self.finish.pop(0) if self.finish else "stop",
                }
            ],
            "usage": {"prompt_tokens": 700, "completion_tokens": 300},
        }

    def questions(self, call: int = 0) -> list[str]:
        """The numbered questions of a call, without their number."""
        user = self.payloads[call]["messages"][1]["content"]
        lines = user.split("Questions :\n", 1)[1].splitlines()
        return [line.split(". ", 1)[1] for line in lines]

    def existing(self, call: int = 0) -> list[str]:
        user = self.payloads[call]["messages"][1]["content"]
        block = user.split("Thèmes existants :\n", 1)[1].split("\n\nQuestions", 1)[0]
        return [line[2:] for line in block.splitlines() if line.startswith("- ")]


@pytest.fixture
def llm(monkeypatch):
    def install(*answers: str | Exception, finish: list[str] | None = None) -> FakeLLM:
        fake = FakeLLM(*answers, finish=finish)
        monkeypatch.setattr(themes, "chat_completion", fake)
        return fake

    return install


class TestNames:
    def test_fold_ignores_case_accents_and_punctuation(self):
        assert themes.fold("Logement étudiant !") == themes.fold("logement ETUDIANT")
        assert themes.fold("Études à l’étranger") == themes.fold("etudes a l'etranger")
        assert themes.fold("???") == ""

    def test_clean_name(self):
        assert themes.clean_name("  « logement   étudiant ».") == "Logement étudiant"
        assert themes.clean_name("<b>Bourses</b> et CROUS") == "Bourses et CROUS"
        assert themes.clean_name("<script>alert(1)</script>") == "Alert(1)"
        assert themes.clean_name("Études à l’étranger") == "Études à l'étranger"
        assert themes.clean_name("Vie\nétudiante") == "Vie étudiante"
        for nothing in ("", " ... ", "<>", None, 3, ["Logement"]):
            assert themes.clean_name(nothing) is None

    def test_a_long_name_is_cut_on_a_word(self):
        name = themes.clean_name("Très " * 30)
        assert name is not None and len(name) <= themes.MAX_NAME and not name.endswith(" ")
        assert name.endswith("Très") or name.endswith("très")

    def test_extract_json(self):
        assert themes.extract_json('```json\n{"1": "A"}\n```') == {"1": "A"}
        assert themes.extract_json('Bien sûr ! {"1": "A"} Bonne journée.') == {"1": "A"}
        assert themes.extract_json("pas de JSON") is None
        assert themes.extract_json('["A", "B"]') is None

    def test_parse(self):
        existing = ["Logement étudiant", "Date de rentrée"]
        fenced = (
            'Voici :\n```json\n{"1": "logement ETUDIANT", "2": "<b>Bourses</b>", "9": "x"}\n```'
        )
        assert themes.parse(fenced, 3, existing) == {1: "Logement étudiant", 2: "Bourses"}
        assert themes.parse('{"1.": "Vie sur le campus", "2": "vie sur le  campus"}', 2, []) == {
            1: "Vie sur le campus",
            2: "Vie sur le campus",
        }
        assert themes.parse('{"1": 3, "2": "", "x": "A", "0": "B"}', 2, []) == {}
        assert themes.parse("rien", 2, existing) == {}

    def test_messages(self):
        messages = themes.build_messages(["Une\nquestion  ?", "x" * 500], [])
        assert messages[0]["content"] == themes.SYSTEM_PROMPT
        user = messages[1]["content"]
        assert "Thèmes existants :\n(aucun)" in user
        assert "1. Une question ?" in user
        assert user.endswith(f"2. {'x' * themes.MAX_QUESTION}")


class TestGrouping:
    def test_the_recorded_runs_group_the_fictive_questions(self, llm):
        """The two answers recorded at the calibration: the second half reuses the themes of
        the first and only adds the one kept out of it on purpose (abroad)."""
        first, second = RUNS
        expected: dict[int, str] = {}
        for question, label in zip(first["questions"], first["expected"], strict=True):
            expected[refused(question)] = label
        fake = llm(first["raw"])

        result = themes.group_pending()

        assert (result.grouped, result.calls, result.error, result.remaining) == (19, 1, None, 0)
        assert (result.tokens_in, result.tokens_out) == (700, 300)
        assert fake.timeouts == [themes.TIMEOUT_S]
        payload = fake.payloads[0]
        assert payload["temperature"] == 0 and payload["max_tokens"] == themes.MAX_TOKENS
        assert payload["model"] == settings.mammouth_chat_model
        assert fake.existing() == ["Autres écoles", "Hors sujet"]  # the fixed themes, always
        assert fake.questions() == [" ".join(q.split()) for q in first["questions"]]
        names = theme_rows()
        assert names["Autres écoles"] == names["Hors sujet"] == "hors_sujet"
        assert names["Logement étudiant"] is None  # never decided by the code
        injection = next(i for i, q in enumerate(first["questions"]) if "consignes" in q)
        assert theme_of(list(expected)[injection]) == "Logement étudiant"

        for question, label in zip(second["questions"], second["expected"], strict=True):
            expected[refused(question)] = label
        fake = llm(second["raw"])

        result = themes.group_pending()

        assert result.grouped == 21 and result.new_themes == ["Études et stages à l'étranger"]
        assert set(fake.existing()) == set(second["existing"])
        by_theme: dict[str, set[str]] = {}
        for entry_id, label in expected.items():
            by_theme.setdefault(theme_of(entry_id) or "", set()).add(label)
        assert len(by_theme) == 11 and "" not in by_theme
        assert all(len(labels) == 1 for labels in by_theme.values())  # no theme mixes topics

    def test_a_question_asked_several_times_goes_once(self, llm):
        ids = [refused("Quand a lieu la rentrée ?"), refused("quand a lieu la RENTREE")]
        ids.append(refused("Logement ?"))
        ids.append(refused("Quand a lieu la rentrée"))
        assert themes.pending_counts() == {"questions": 4, "distinct": 2, "next_batch": 4}
        fake = llm('{"1": "Date de rentrée", "2": "Logement étudiant"}')

        result = themes.group_pending()

        assert fake.questions() == ["Quand a lieu la rentrée ?", "Logement ?"]
        assert result.grouped == 4
        assert [theme_of(i) for i in ids] == ["Date de rentrée"] * 2 + [
            "Logement étudiant",
            "Date de rentrée",
        ]

    def test_only_the_questions_without_an_answer_are_grouped(self, llm):
        store.record(channel="chat", question="Combien ?", result=ANSWERED)
        store.record(
            channel="chat",
            question="Bonjour",
            result={"grade": "ok", "answer": "Bonjour !", "retrieved": [], "sources": []},
        )
        store.record(channel="chat", question="x", error="LLM down")
        store.record(
            channel="api",
            question="Et pour le BTS ?",
            result={**ANSWERED, "answer": DOES_NOT_KNOW, "rewritten": "Le BTS est-il éligible ?"},
        )
        fake = llm('{"1": "Parcoursup"}')

        assert themes.group_pending().grouped == 1
        assert fake.questions() == ["Le BTS est-il éligible ?"]  # the standalone rewrite

    def test_a_batch_holds_at_most_batch_size_questions(self, llm):
        for number in range(themes.BATCH_SIZE + 20):
            refused(f"Question numéro {number}")
        assert themes.pending_counts()["next_batch"] == themes.BATCH_SIZE
        everything = {str(n): "Divers" for n in range(1, themes.BATCH_SIZE + 1)}
        fake = llm(yaml.safe_dump(everything))  # not JSON: nothing written
        assert themes.group_pending().error == "invalid"
        fake = llm(str(everything).replace("'", '"'))

        result = themes.group_pending()

        assert len(fake.questions()) == themes.BATCH_SIZE
        assert (result.grouped, result.remaining) == (themes.BATCH_SIZE, 20)
        assert themes.group_pending().grouped == 20 and len(fake.questions(1)) == 20

    def test_an_answer_cut_by_max_tokens_is_asked_again_for_half_the_batch(self, llm):
        ids = [refused(f"Question {n}") for n in range(8)]
        fake = llm('{"1": "Coupé', '{"1": "A", "2": "B", "3": "A", "4": "B"}', finish=["length"])

        result = themes.group_pending()

        assert result.calls == 2 and result.grouped == 4 and result.error is None
        assert [len(fake.questions(call)) for call in range(2)] == [8, 4]
        assert [theme_of(i) for i in ids[:5]] == ["A", "B", "A", "B", None]

    def test_an_answer_always_cut_writes_nothing(self, llm):
        refused("Question A")
        refused("Question B")
        fake = llm('{"1": "Coupé', finish=["length"] * 5)

        result = themes.group_pending()

        assert result.error == "cut" and result.grouped == 0 and theme_rows() == {}
        assert [len(fake.questions(call)) for call in range(len(fake.payloads))] == [2, 1]

    def test_an_unavailable_llm_writes_nothing(self, llm):
        refused("Question A")
        llm(LLMUnavailableError("429 budget"))

        result = themes.group_pending()

        assert (result.error, result.grouped, result.calls, result.remaining) == ("llm", 0, 0, 1)
        assert theme_rows() == {}

    def test_an_answer_without_choices_counts_as_unavailable(self, llm, monkeypatch):
        refused("Question A")
        monkeypatch.setattr(themes, "chat_completion", lambda *_args, **_kwargs: {"error": "x"})
        assert themes.group_pending().error == "llm"

    def test_unknown_numbers_and_bad_names_leave_the_question_pending(self, llm):
        ids = [refused("Question A"), refused("Question B"), refused("Question C")]
        llm('{"1": "<i>Thème</i> A", "2": "", "7": "Fantôme"}')

        result = themes.group_pending()

        assert result.grouped == 1 and result.remaining == 2
        assert [theme_of(i) for i in ids] == ["Thème A", None, None]
        assert "Fantôme" not in theme_rows()

    def test_an_existing_theme_is_reused_whatever_its_spelling(self, llm):
        themes.move(refused("Logement ?"), new_name="Logement étudiant")
        entry_id = refused("Une chambre à Lyon ?")
        fake = llm('{"1": "logement ETUDIANT"}')

        result = themes.group_pending()

        assert result.new_themes == [] and theme_of(entry_id) == "Logement étudiant"
        assert "Logement étudiant" in fake.existing()

    def test_one_grouping_at_a_time(self, llm):
        refused("Question A")
        fake = llm('{"1": "A"}')
        with themes._lock:
            assert themes.group_pending().error == "busy"
        assert fake.payloads == []
        assert themes.group_pending().grouped == 1

    def test_nothing_pending_calls_nothing(self, llm):
        fake = llm('{"1": "A"}')
        result = themes.group_pending()
        assert (result.grouped, result.calls, result.error) == (0, 0, None)
        assert fake.payloads == []

    def test_the_command_groups_batch_after_batch(self, llm, capsys):
        for number in range(themes.BATCH_SIZE + 1):
            refused(f"Question numéro {number}")
        all_divers = {str(n): "Divers" for n in range(1, themes.BATCH_SIZE + 1)}
        fake = llm(str(all_divers).replace("'", '"'))

        themes.main()

        assert len(fake.payloads) == 2 and themes.pending_counts()["questions"] == 0
        out = capsys.readouterr().out
        assert "100 questions grouped" in out and "1 questions grouped" in out


def add_to(theme: str, question: str, **kwargs) -> int:
    entry_id = refused(question, **kwargs)
    assert themes.move(entry_id, new_name=theme) is None
    return entry_id


class TestReading:
    def test_the_themes_with_their_counts(self):
        add_to("Logement étudiant", "Un logement ?", thread_id="t1")
        add_to("Logement étudiant", "un LOGEMENT", thread_id="t1")
        add_to("Logement étudiant", "Une chambre ?", channel="api")
        latest = add_to("Logement étudiant", "Une résidence ?", thread_id="t2")
        add_to("Date de rentrée", "Rentrée ?", thread_id="t3")
        store.record(
            channel="chat",
            question="Parcoursup ?",
            result={**ANSWERED, "answer": DOES_NOT_KNOW},
            thread_id="t4",
        )
        assert themes.move(last_id(), new_name="Date de rentrée") is None

        found = themes.list_themes()

        assert [t["name"] for t in found] == ["Logement étudiant", "Date de rentrée"]
        housing, start = found
        assert (housing["questions"], housing["conversations"]) == (4, 3)
        assert housing["example"] == "un LOGEMENT"  # asked twice (folded), the latest of the two
        assert housing["by_kind"] == {"refus": 4}
        assert start["by_kind"] == {"refus": 1, "aveu": 1}
        assert housing["last"] >= housing["first"] and housing["cause"] is None
        assert themes.get_theme(housing["id"])["entries"][0]["id"] == latest

    def test_a_single_question_is_its_own_example(self):
        add_to("Logement étudiant", "Un logement ?")
        newest = add_to("Logement étudiant", "Une chambre ?")
        assert themes.list_themes()[0]["example_id"] == newest

    def test_the_period_hides_the_themes_without_a_recent_question(self):
        old = add_to("Vieux thème", "Ancienne question")
        add_to("Logement étudiant", "Un logement ?")
        with db() as conn:
            conn.execute(
                "UPDATE answer_log SET created_at = '2026-01-01T00:00:00+00:00' WHERE id = ?",
                (old,),
            )
        assert [t["name"] for t in themes.list_themes("7")] == ["Logement étudiant"]
        assert len(themes.list_themes()) == 2

    def test_the_questions_not_grouped_yet(self):
        refused("Pas encore rangée")
        add_to("Logement étudiant", "Un logement ?")
        store.record(channel="chat", question="Combien ?", result=ANSWERED)
        total, rows = themes.unthemed()
        assert total == 1 and rows[0]["text"] == "Pas encore rangée" and rows[0]["kind"] == "refus"

    def test_suggested_cause(self):
        school = themes.get_theme(theme_id_of(add_to("Autres écoles", "HEC ?")))
        assert school["suggested_cause"] == "hors_sujet"
        mixed = add_to("Divers", "Une question ?")
        assert themes.get_theme(theme_id_of(mixed))["suggested_cause"] is None
        for _ in range(2):
            store.record(
                channel="chat",
                question="Et Polytechnique ?",
                result={**ANSWERED, "answer": "Je ne peux répondre qu'aux questions sur Ynov."},
            )
            themes.move(last_id(), new_name="Divers")
        assert themes.get_theme(theme_id_of(mixed))["suggested_cause"] == "hors_sujet"

    def test_an_unknown_theme(self):
        assert themes.get_theme(999) is None

    def test_current_search_keeps_one_hit_per_section(self, monkeypatch):
        from graph.nodes import retrieve

        hits = [
            {"source": "a.html", "section": "Tarifs", "score": 0.6, "metadata": {"title": "A"}},
            {"source": "a.html", "section": "Tarifs", "score": 0.5, "metadata": {}},
        ] + [{"source": f"{n}.html", "section": "S", "score": 0.4} for n in range(10)]
        monkeypatch.setattr(retrieve, "search", lambda *_args: hits)
        found = themes.current_search("Un logement ?")
        assert len(found) == 5 and found[0]["title"] == "A"
        assert [f["source"] for f in found[:2]] == ["a.html", "0.html"]


class TestDecisions:
    def test_rename(self):
        housing = theme_id_of(add_to("Logement", "Un logement ?"))
        add_to("Date de rentrée", "Rentrée ?")
        assert themes.rename(housing, "  Logement   étudiant ") is None
        assert themes.get_theme(housing)["name"] == "Logement étudiant"
        assert themes.rename(housing, "date de RENTREE") == (
            "Le thème « Date de rentrée » existe déjà : fusionnez plutôt les deux thèmes."
        )
        assert themes.rename(housing, "logement étudiant !") is None  # its own name, re-spelt
        assert themes.rename(housing, " <> ") == "Le nom est vide."
        assert themes.rename(999, "Nouveau") == "Thème introuvable."

    def test_cause_and_note(self):
        housing = theme_id_of(add_to("Logement", "Un logement ?"))
        assert themes.set_cause(housing, "contenu", "  Pas de page logement.  ")
        found = themes.get_theme(housing)
        assert (found["cause"], found["note"]) == ("contenu", "Pas de page logement.")
        assert themes.set_cause(housing, None, "")
        assert themes.get_theme(housing)["cause"] is None
        assert not themes.set_cause(999, "contenu")
        with pytest.raises(ValueError):
            themes.set_cause(housing, "autre")

    def test_merge(self):
        source_entry = add_to("Logement", "Un logement ?")
        source = theme_id_of(source_entry)
        target = theme_id_of(add_to("Logement étudiant", "Une chambre ?"))
        themes.set_cause(source, "contenu", "Note de la source")
        assert not themes.merge(source, source) and not themes.merge(source, 999)
        assert themes.merge(source, target)
        assert themes.get_theme(source) is None
        merged = themes.get_theme(target)
        assert merged["questions"] == 2 and theme_of(source_entry) == "Logement étudiant"
        assert (merged["cause"], merged["note"]) == ("contenu", "Note de la source")

    def test_move(self):
        entry_id = add_to("Logement", "Un logement ?")
        other = theme_id_of(add_to("Date de rentrée", "Rentrée ?"))
        assert themes.move(entry_id, other) is None and theme_of(entry_id) == "Date de rentrée"
        assert themes.move(entry_id, new_name="date de rentrée") is None  # the existing one
        assert len(theme_rows()) == 2
        assert themes.move(entry_id, new_name="Nouveau thème") is None
        assert theme_of(entry_id) == "Nouveau thème"
        assert themes.move(entry_id) is None and theme_of(entry_id) is None  # pending again
        assert themes.pending_counts()["questions"] == 1
        assert themes.move(entry_id, 999) == "Thème introuvable."
        assert themes.move(entry_id, new_name="<>") == "Le nom est vide."
        store.record(channel="chat", question="Combien ?", result=ANSWERED)
        assert themes.move(last_id(), other) == (
            "Cette réponse n'est pas une question sans réponse."
        )
        assert themes.move(999, other) == "Cette réponse n'est pas une question sans réponse."

    def test_choices_are_sorted_by_name(self):
        add_to("Zèbre", "Z ?")
        add_to("école", "E ?")
        add_to("Avion", "A ?")
        assert [t["name"] for t in themes.choices()] == ["Avion", "École", "Zèbre"]


class TestMigration:
    @staticmethod
    def _old_database() -> None:
        """The schema of #19: answer_log without gap_theme_id, no gap_theme table."""
        schema = SCHEMA.read_text(encoding="utf-8")
        added = "    feedback_at TEXT,\n    gap_theme_id INTEGER\n"
        old = schema.replace(added, "    feedback_at TEXT\n")
        start = old.index("CREATE TABLE IF NOT EXISTS gap_theme")
        old = old[:start] + old[old.index(");", start) + 2 :]
        assert "gap_theme_id INTEGER" not in old and "EXISTS gap_theme" not in old
        with sqlite3.connect(settings.chat_db_path) as conn:
            conn.executescript(old)

    def test_an_older_database_gets_the_column_the_index_and_the_table(
        self, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "old.db"))
        self._old_database()
        refused("Une question d'avant")

        with caplog.at_level(logging.INFO, logger="chat.db"):
            init_db()

        with db() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(answer_log)")}
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(answer_log)")}
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        assert "gap_theme_id" in columns and "idx_answer_log_gap_theme" in indexes
        assert "gap_theme" in tables
        assert "gap_theme_id column added" in caplog.text
        assert "feedbacks copied" not in caplog.text  # only the feedback columns copy data
        assert themes.pending_counts()["questions"] == 1

        caplog.clear()
        with caplog.at_level(logging.INFO, logger="chat.db"):
            init_db()
        assert "added" not in caplog.text

    def test_a_new_database_has_them(self):
        with db() as conn:
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(answer_log)")}
        assert "idx_answer_log_gap_theme" in indexes
        assert themes.list_themes() == [] and themes.choices() == []
