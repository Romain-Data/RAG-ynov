"""The journal week by week and the configurations it saw, for the dashboard (#16)."""

from datetime import UTC, datetime, timedelta

from app.core.config import settings
from chat.db import db
from journal import review, stats, store

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)  # a Wednesday: its week begins on the 12th
THIS_WEEK = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
ANSWERED = "Environ 7 000 € par an [Source 1]."
DOES_NOT_KNOW = "Le contexte ne précise pas quels BTS sont accessibles via Parcoursup."
REFUSED = {"grade": "refuse", "retrieved": [], "sources": []}
HELLO = {"answer": "Bonjour !", "grade": "ok", "retrieved": [], "sources": []}


def add(
    when: datetime,
    answer: str = ANSWERED,
    *,
    result: dict | None = None,
    channel: str = "chat",
    error: str | None = None,
    latency_ms: int | None = None,
    llm_model: str = "mistral-medium-2508",
    tokens: tuple[int, int] = (1200, 80),
) -> int:
    """One entry of the journal written at `when`: a generated answer unless `result` (a
    refusal, a greeting) or `error` say otherwise."""
    state = result or {
        "answer": answer,
        "grade": "ok",
        "sources": [{"source": "bts-sio.html", "section": "Tarifs"}],
        "retrieved": [{"source": "bts-sio.html", "section": "Tarifs", "score": 0.62}],
        "llm_model": llm_model,
        "tokens_in": tokens[0],
        "tokens_out": tokens[1],
    }
    store.record(
        channel=channel,
        question="Combien coûte le BTS SIO ?",
        result=None if error else state,
        error=error,
        latency_ms=latency_ms,
    )
    with db() as conn:
        entry_id = int(conn.execute("SELECT MAX(id) FROM answer_log").fetchone()[0])
        conn.execute(
            "UPDATE answer_log SET created_at = ? WHERE id = ?", (when.isoformat(), entry_id)
        )
    return entry_id


def rate(entry_id: int, value: int, comment: str | None = None) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE answer_log SET feedback = ?, feedback_comment = ? WHERE id = ?",
            (value, comment, entry_id),
        )


def set_column(entry_id: int, column: str, value: object) -> None:
    with db() as conn:
        conn.execute(f"UPDATE answer_log SET {column} = ? WHERE id = ?", (value, entry_id))


class TestWeeks:
    def test_an_empty_journal_gives_no_week(self):
        assert stats.weekly(now=NOW) == []

    def test_a_single_week(self):
        add(THIS_WEEK)
        weeks = stats.weekly(now=NOW)
        assert len(weeks) == 1
        assert weeks[0]["start"] == "2026-10-12" and weeks[0]["end"] == "2026-10-19"
        assert weeks[0]["week"] == "2026-W42"

    def test_from_the_first_week_with_the_empty_ones(self):
        add(THIS_WEEK - timedelta(days=14))
        add(THIS_WEEK)
        weeks = stats.weekly(now=NOW)
        assert [w["start"] for w in weeks] == ["2026-09-28", "2026-10-05", "2026-10-12"]
        empty = weeks[1]
        assert empty["questions"] == {"chat": 0, "api": 0}
        assert empty["smalltalk"] == empty["refused"] == empty["errors"] == 0
        assert empty["gaps"]["questions"] == 0 and empty["gaps"]["flagged"] == 0
        assert set(empty["feedback"].values()) == {0}
        assert empty["reviewed"] == 0 and set(empty["reviews"].values()) == {0}
        assert empty["latency_ms_median"] is None
        assert empty["tokens_in_avg"] is None and empty["tokens_out_avg"] is None

    def test_an_older_journal_is_cut_to_the_last_weeks(self):
        add(THIS_WEEK - timedelta(weeks=20))
        add(THIS_WEEK)
        assert len(stats.weekly(now=NOW)) == stats.WEEKS == 12
        weeks = stats.weekly(weeks=3, now=NOW)
        assert [w["start"] for w in weeks] == ["2026-09-28", "2026-10-05", "2026-10-12"]

    def test_monday_midnight_begins_a_new_week(self):
        add(datetime(2026, 10, 11, 23, 59, tzinfo=UTC))  # Sunday
        add(datetime(2026, 10, 12, 0, 0, tzinfo=UTC))  # Monday
        before, after = stats.weekly(now=NOW)
        assert before["questions"]["chat"] == 1 and after["questions"]["chat"] == 1

    def test_the_current_week_by_default(self):
        store.record(channel="chat", question="Bonjour", result=HELLO)  # written now
        weeks = stats.weekly()
        assert len(weeks) == 1 and weeks[0]["smalltalk"] == 1


class TestFigures:
    def test_greetings_apart_and_questions_per_channel(self):
        add(THIS_WEEK)
        add(THIS_WEEK, channel="api")
        add(THIS_WEEK, result=REFUSED)
        add(THIS_WEEK, result=HELLO)
        add(THIS_WEEK, error="LLMUnavailableError: 429")
        week = stats.weekly(now=NOW)[0]
        assert week["questions"] == {"chat": 3, "api": 1}  # the error is a question asked
        assert week["smalltalk"] == 1 and week["refused"] == 1 and week["errors"] == 1

    def test_the_questions_without_an_answer_are_those_of_gaps_between(self):
        add(THIS_WEEK - timedelta(days=7), DOES_NOT_KNOW)
        add(THIS_WEEK - timedelta(days=7))
        add(THIS_WEEK, DOES_NOT_KNOW)
        add(THIS_WEEK, result=REFUSED)
        add(THIS_WEEK, f"{ANSWERED} Le contexte ne précise pas la rentrée.")
        rate(add(THIS_WEEK), 0)
        add(THIS_WEEK, result=HELLO)
        weeks = stats.weekly(now=NOW)
        for week in weeks:
            start = datetime.fromisoformat(week["start"]).replace(tzinfo=UTC)
            assert week["gaps"] == stats.gaps_between(
                start.isoformat(), (start + timedelta(days=7)).isoformat()
            )
        assert weeks[0]["gaps"]["by_kind"]["aveu"] == 1
        assert weeks[1]["gaps"]["questions"] == 4  # without the greeting
        assert weeks[1]["gaps"]["without_answer"] == 2  # the admission and the refusal
        assert weeks[1]["gaps"]["by_kind"]["incomplete"] == 1
        assert weeks[1]["gaps"]["by_kind"]["pas_utile"] == 1

    def test_the_thumbs_without_the_greetings_nor_the_api(self):
        rate(add(THIS_WEEK), 1, "Merci")
        rate(add(THIS_WEEK), 0)
        rate(add(THIS_WEEK, result=REFUSED), 0)
        rate(add(THIS_WEEK, result=HELLO), 1)  # says nothing about the answers
        add(THIS_WEEK)  # not rated
        add(THIS_WEEK, channel="api")  # no thumbs on the API
        feedback = stats.weekly(now=NOW)[0]["feedback"]
        assert feedback == {"answers": 4, "rated": 3, "useful": 1, "not_useful": 2, "comments": 1}
        assert feedback == stats.summary()["feedback"]["total_without_smalltalk"]

    def test_the_reviews_of_the_questions_of_the_week(self):
        review.review(add(THIS_WEEK), "bonne")
        review.review(add(THIS_WEEK), "bonne")
        review.review(add(THIS_WEEK), "fausse")
        review.review(add(THIS_WEEK - timedelta(days=7)), "partielle")
        add(THIS_WEEK)
        before, week = stats.weekly(now=NOW)
        assert week["reviewed"] == 3
        assert week["reviews"] == {"bonne": 2, "partielle": 0, "fausse": 1, "hors_sujet": 0}
        assert before["reviews"]["partielle"] == 1

    def test_the_median_latency_of_the_generated_answers(self):
        add(THIS_WEEK, latency_ms=1000)
        add(THIS_WEEK, latency_ms=3000)
        add(THIS_WEEK, latency_ms=2000)
        add(THIS_WEEK, result=REFUSED, latency_ms=90)  # no LLM: left out
        add(THIS_WEEK)  # latency unknown
        assert stats.weekly(now=NOW)[0]["latency_ms_median"] == 2000
        add(THIS_WEEK, latency_ms=5000)
        assert stats.weekly(now=NOW)[0]["latency_ms_median"] == 2500

    def test_the_tokens_of_the_generated_answers(self):
        add(THIS_WEEK, tokens=(1000, 100))
        add(THIS_WEEK, tokens=(3000, 300))
        add(THIS_WEEK, result=REFUSED)
        week = stats.weekly(now=NOW)[0]
        assert week["tokens_in_avg"] == 2000 and week["tokens_out_avg"] == 200


class TestConfigChanges:
    @staticmethod
    def _values(field: str) -> list:
        found = {c["field"]: c for c in stats.config_changes()}
        return [v["value"] for v in found[field]["values"]]

    def test_an_empty_journal(self):
        changes = stats.config_changes()
        assert [c["field"] for c in changes] == list(stats.CONFIG_FIELDS)
        assert all(c["values"] == [] for c in changes)
        assert changes[0]["label"] == "Modèle du LLM"

    def test_a_change_of_model_and_of_collection(self):
        old = [add(THIS_WEEK - timedelta(days=9), llm_model="mistral-medium-3-5") for _ in "ab"]
        for entry_id in old:
            set_column(entry_id, "collection", "ynov_rag_v3")
        refused = add(THIS_WEEK - timedelta(days=8), result=REFUSED)
        set_column(refused, "collection", "ynov_rag_v3")
        add(THIS_WEEK, llm_model="mammouth-recommended")
        add(THIS_WEEK, result=REFUSED)
        assert self._values("llm_model") == ["mistral-medium-3-5", "mammouth-recommended"]
        assert self._values("collection") == ["ynov_rag_v3", settings.qdrant_collection_name]
        found = {c["field"]: c for c in stats.config_changes()}
        first = found["collection"]["values"][0]
        assert first["n"] == 3  # the refusal counts: it went through the collection
        assert first["first"] == (THIS_WEEK - timedelta(days=9)).isoformat()
        assert first["last"] == (THIS_WEEK - timedelta(days=8)).isoformat()
        assert len(found["threshold"]["values"]) == 1  # no change

    def test_the_entries_without_an_llm_do_not_count_as_a_model(self):
        add(THIS_WEEK, result=REFUSED)
        add(THIS_WEEK, result=HELLO)
        add(THIS_WEEK, error="LLMUnavailableError: 429")
        assert self._values("llm_model") == []
        assert len(self._values("collection")) == 1

    def test_the_version_when_coolify_gives_it(self):
        add(THIS_WEEK)
        assert self._values("app_version") == []  # SOURCE_COMMIT not set
        set_column(add(THIS_WEEK), "app_version", "61c1240")
        assert self._values("app_version") == ["61c1240"]
