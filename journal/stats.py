"""Figures about the journal for the /admin summary page (#18): how the answers end, how they
were reviewed, which model answered, the scores that tell whether the threshold fits, what
the users of the chat thought of the answers (their thumbs, #19) and which questions went
without an answer (#20); the same figures week by week, and the configurations seen in the
journal, for the dashboard of #16.

Plain dictionaries of counts, so that the dashboard of #16 can reuse them as they are."""

import sqlite3
import statistics
from datetime import UTC, datetime, timedelta

from chat.db import db
from journal.gaps import GAP_KINDS, WITHOUT_ANSWER
from journal.review import REVIEW_LABELS

PERIODS = ("7", "30")  # days; anything else means the whole journal
DAYS_SHOWN = 14  # lines of the per-day table
ERRORS_SHOWN = 5
FEEDBACK_COUNTS = ("answers", "rated", "useful", "not_useful", "comments")
# Only the chat has thumbs: the answers of the API would lower the share rated
FEEDBACK_BY_ROUTE = (
    "SELECT route, COUNT(*) AS answers, COUNT(feedback) AS rated, "
    "SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) AS useful, "
    "SUM(CASE WHEN feedback = 0 THEN 1 ELSE 0 END) AS not_useful, "
    "COUNT(feedback_comment) AS comments "
    "FROM answer_log WHERE channel = 'chat'{clause} GROUP BY route"
)
WEEKS = 12  # weeks of the dashboard
# What answered, in the journal: column -> label of the dashboard
CONFIG_FIELDS = {
    "llm_model": "Modèle du LLM",
    "collection": "Collection",
    "embedding_model": "Modèle d'embedding",
    "threshold": "Seuil",
    "app_version": "Version",
}


def _gaps(by_kind: list[dict]) -> dict:
    """The questions left without an answer, per kind (journal/gaps.py), out of the questions
    that went to the search: greetings and errors are left out of both. `without_answer` is
    the kinds that got no answer at all; the incomplete and "Pas utile" ones come apart."""
    counts = {r["kind"]: r["n"] for r in by_kind}
    kinds = {kind: counts.get(kind, 0) for kind in GAP_KINDS}
    return {
        "questions": sum(counts.values()),
        "by_kind": kinds,
        "without_answer": sum(kinds[kind] for kind in WITHOUT_ANSWER),
        "flagged": sum(kinds.values()),
    }


def _between(start: str | None, end: str | None) -> tuple[str, dict]:
    """The SQL condition " AND created_at …" from `start` (included) to `end` (excluded), ISO
    dates, either of them None, and its parameters."""
    clause, params = "", {}
    if start:
        clause += " AND created_at >= :start"
        params["start"] = start
    if end:
        clause += " AND created_at < :end"
        params["end"] = end
    return clause, params


def gaps_between(start: str | None, end: str | None) -> dict:
    """The questions left without an answer (see _gaps) from `start` (included) to `end`
    (excluded), ISO dates; either may be None. Shared by the summary, the monthly report and
    the weeks of the dashboard."""
    clause, params = _between(start, end)
    with db() as conn:
        conn.row_factory = sqlite3.Row
        # kind None: the question got an answer
        rows = conn.execute(
            "SELECT gap_kind(route, answer, feedback) AS kind, COUNT(*) AS n FROM answer_log "
            f"WHERE route IN ('generate', 'refuse'){clause} GROUP BY kind",
            params,
        ).fetchall()
    return _gaps([dict(row) for row in rows])


def _feedback(by_route: list[dict], crosstab: list[dict]) -> dict:
    """The thumbs of the chat: counts per route, their total without the replies to greetings
    (a "Utile" under "Bonjour !" says nothing about the answers), and thumbs x review."""
    routes = {r["route"]: {key: r[key] or 0 for key in FEEDBACK_COUNTS} for r in by_route}
    total = {
        key: sum(line[key] for route, line in routes.items() if route != "smalltalk")
        for key in FEEDBACK_COUNTS
    }
    return {
        "by_route": routes,
        "total_without_smalltalk": total,
        "comments": sum(line["comments"] for line in routes.values()),
        # (1 "Utile" or 0 "Pas utile", review label or "" for "not reviewed yet") -> count
        "crosstab": {(r["feedback"], r["label"]): r["n"] for r in crosstab},
    }


def since(period: str) -> str | None:
    """The ISO date `period` days ago ("7", "30"), or None for the whole journal."""
    if period not in PERIODS:
        return None
    return (datetime.now(UTC) - timedelta(days=int(period))).isoformat()


def summary(period: str = "") -> dict:
    """Aggregates over the entries of the last `period` days ("7", "30"), or of all of them."""
    since_date = since(period)
    where = "WHERE created_at >= :since" if since_date else ""
    and_ = "AND" if since_date else "WHERE"
    params = {"since": since_date} if since_date else {}
    with db() as conn:
        conn.row_factory = sqlite3.Row

        def rows(sql: str) -> list[dict]:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

        totals = rows(
            f"SELECT COUNT(*) AS total, MIN(created_at) AS first, MAX(created_at) AS last, "
            f"SUM(review_label IS NOT NULL) AS reviewed, SUM(promoted_as IS NOT NULL) AS promoted "
            f"FROM answer_log {where}"
        )[0]
        by_route = rows(
            f"SELECT route, COUNT(*) AS n, AVG(top_score) AS avg_score, "
            f"MIN(top_score) AS min_score, MAX(top_score) AS max_score "
            f"FROM answer_log {where} GROUP BY route"
        )
        # route x review label, "" standing for "not reviewed yet"
        crosstab = rows(
            f"SELECT route, COALESCE(review_label, '') AS label, COUNT(*) AS n "
            f"FROM answer_log {where} GROUP BY route, label"
        )
        by_label = rows(
            f"SELECT review_label AS label, COUNT(*) AS n, AVG(top_score) AS avg_score, "
            f"MIN(top_score) AS min_score, MAX(top_score) AS max_score FROM answer_log "
            f"{where} {and_} review_label IS NOT NULL GROUP BY review_label"
        )
        by_model = rows(
            f"SELECT COALESCE(llm_model, '') AS model, COUNT(*) AS n, "
            f"AVG(latency_ms) AS avg_latency, AVG(tokens_in) AS avg_in, "
            f"AVG(tokens_out) AS avg_out, MIN(created_at) AS first, MAX(created_at) AS last "
            f"FROM answer_log "
            f"{where} {and_} route IN ('generate', 'error') GROUP BY model ORDER BY n DESC"
        )
        per_day = rows(
            f"SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n, "
            f"SUM(route = 'refuse') AS refused, SUM(route = 'error') AS errors "
            f"FROM answer_log {where} GROUP BY day ORDER BY day DESC LIMIT {DAYS_SHOWN}"
        )
        errors = rows(
            f"SELECT substr(error, 1, 120) AS cause, COUNT(*) AS n, MAX(created_at) AS last "
            f"FROM answer_log {where} {and_} error IS NOT NULL GROUP BY cause "
            f"ORDER BY n DESC LIMIT {ERRORS_SHOWN}"
        )
        feedback_by_route = rows(
            FEEDBACK_BY_ROUTE.format(clause=" AND created_at >= :since" if since_date else "")
        )
        feedback_crosstab = rows(
            f"SELECT feedback, COALESCE(review_label, '') AS label, COUNT(*) AS n "
            f"FROM answer_log {where} {and_} feedback IS NOT NULL GROUP BY feedback, label"
        )
    return {
        "period": period if since_date else "",
        "totals": totals,
        "by_route": {r["route"]: r for r in by_route},
        "crosstab": {(r["route"], r["label"]): r["n"] for r in crosstab},
        "by_label": {r["label"]: r for r in by_label if r["label"] in REVIEW_LABELS},
        "by_model": by_model,
        "per_day": per_day,
        "errors": errors,
        "feedback": _feedback(feedback_by_route, feedback_crosstab),
        "gaps": gaps_between(since_date, None),
    }


def week_start(moment: datetime) -> datetime:
    """Monday 00:00 UTC of the ISO week of `moment`."""
    day = moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=day.weekday())


def _week(conn: sqlite3.Connection, start: datetime) -> dict:
    """The figures of the week that begins on `start`, with the definitions of summary():
    greetings apart, thumbs without the greetings (_feedback), questions without an answer
    (gaps_between)."""
    end = start + timedelta(days=7)
    clause, params = _between(start.isoformat(), end.isoformat())

    def rows(sql: str) -> list[dict]:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    counts = rows(
        "SELECT SUM(route != 'smalltalk' AND channel = 'chat') AS chat, "
        "SUM(route != 'smalltalk' AND channel = 'api') AS api, "
        "SUM(route = 'smalltalk') AS smalltalk, SUM(route = 'refuse') AS refused, "
        "SUM(route = 'error') AS errors, SUM(review_label IS NOT NULL) AS reviewed, "
        "AVG(CASE WHEN route = 'generate' THEN tokens_in END) AS tokens_in, "
        "AVG(CASE WHEN route = 'generate' THEN tokens_out END) AS tokens_out "
        f"FROM answer_log WHERE 1{clause}"
    )[0]
    labels = {
        r["label"]: r["n"]
        for r in rows(
            "SELECT review_label AS label, COUNT(*) AS n FROM answer_log "
            f"WHERE review_label IS NOT NULL{clause} GROUP BY review_label"
        )
    }
    # The time a user waited for an answer of the LLM: refusals and greetings call no LLM
    latencies = [
        r["latency_ms"]
        for r in rows(
            "SELECT latency_ms FROM answer_log "
            f"WHERE route = 'generate' AND latency_ms IS NOT NULL{clause}"
        )
    ]
    feedback = _feedback(rows(FEEDBACK_BY_ROUTE.format(clause=clause)), [])
    iso = start.isocalendar()
    return {
        "start": start.date().isoformat(),
        "end": end.date().isoformat(),
        "week": f"{iso.year}-W{iso.week:02d}",
        "questions": {"chat": counts["chat"] or 0, "api": counts["api"] or 0},
        "smalltalk": counts["smalltalk"] or 0,
        "refused": counts["refused"] or 0,
        "errors": counts["errors"] or 0,
        "gaps": gaps_between(start.isoformat(), end.isoformat()),
        "feedback": feedback["total_without_smalltalk"],
        "reviewed": counts["reviewed"] or 0,
        "reviews": {label: labels.get(label, 0) for label in REVIEW_LABELS},
        "latency_ms_median": statistics.median(latencies) if latencies else None,
        "tokens_in_avg": counts["tokens_in"],
        "tokens_out_avg": counts["tokens_out"],
    }


def weekly(weeks: int = WEEKS, now: datetime | None = None) -> list[dict]:
    """The figures of each ISO week (Monday 00:00 UTC), oldest first: from the first week of
    the journal, or `weeks` weeks back when it is older, to the current week, empty weeks
    included. An empty journal gives no week.

    A week: `start`, `end` (the next Monday, excluded) and `week` ("2026-W41"); `questions`
    per channel without the greetings (errors included); `smalltalk`, `refused`, `errors`;
    `gaps` as in summary() (gaps_between); `feedback`, the thumbs without the greetings
    (answers, rated, useful, not_useful, comments, as in _feedback); `reviewed` and `reviews`
    per label; `latency_ms_median` of the generated answers; `tokens_in_avg` and
    `tokens_out_avg` of the generated answers (None without one)."""
    current = week_start(now or datetime.now(UTC))
    with db() as conn:
        conn.row_factory = sqlite3.Row
        first = conn.execute("SELECT MIN(created_at) FROM answer_log").fetchone()[0]
        if first is None:
            return []
        start = max(
            week_start(datetime.fromisoformat(first)),
            current - timedelta(weeks=max(weeks, 1) - 1),
        )
        found = []
        while start <= current:
            found.append(_week(conn, start))
            start += timedelta(days=7)
    return found


def config_changes() -> list[dict]:
    """What answered, according to the journal: for each field of CONFIG_FIELDS, `field`,
    `label` and its `values` in the order they appeared, each with `value`, `first`, `last`
    (ISO dates) and `n` entries. A field with two values or more changed.

    Field by field rather than per combination: the entries without an answer of the LLM
    (refusals, greetings, errors) have no `llm_model` and would split every configuration in
    two. Empty values are left out (no `app_version` when Coolify does not give the commit)."""
    found = []
    with db() as conn:
        conn.row_factory = sqlite3.Row
        for field, label in CONFIG_FIELDS.items():
            values = conn.execute(
                f"SELECT {field} AS value, MIN(created_at) AS first, MAX(created_at) AS last, "
                f"COUNT(*) AS n FROM answer_log WHERE {field} IS NOT NULL AND {field} != '' "
                f"GROUP BY {field} ORDER BY first"
            ).fetchall()
            found.append({"field": field, "label": label, "values": [dict(v) for v in values]})
    return found
