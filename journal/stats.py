"""Figures about the journal for the /admin summary page (#18): how the answers end, how they
were reviewed, which model answered, the scores that tell whether the threshold fits, and what
the users of the chat thought of the answers (their thumbs, #19).

Plain dictionaries of counts, so that the dashboard of #16 can reuse them as they are."""

import sqlite3
from datetime import UTC, datetime, timedelta

from chat.db import db
from journal.review import REVIEW_LABELS

PERIODS = ("7", "30")  # days; anything else means the whole journal
DAYS_SHOWN = 14  # lines of the per-day table
ERRORS_SHOWN = 5
FEEDBACK_COUNTS = ("answers", "rated", "useful", "not_useful", "comments")


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


def _since(period: str) -> str | None:
    if period not in PERIODS:
        return None
    return (datetime.now(UTC) - timedelta(days=int(period))).isoformat()


def summary(period: str = "") -> dict:
    """Aggregates over the entries of the last `period` days ("7", "30"), or of all of them."""
    since = _since(period)
    where = "WHERE created_at >= :since" if since else ""
    and_ = "AND" if since else "WHERE"
    params = {"since": since} if since else {}
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
        # Only the chat has thumbs: the answers of the API would lower the share rated
        feedback_by_route = rows(
            f"SELECT route, COUNT(*) AS answers, COUNT(feedback) AS rated, "
            f"SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) AS useful, "
            f"SUM(CASE WHEN feedback = 0 THEN 1 ELSE 0 END) AS not_useful, "
            f"COUNT(feedback_comment) AS comments "
            f"FROM answer_log {where} {and_} channel = 'chat' GROUP BY route"
        )
        feedback_crosstab = rows(
            f"SELECT feedback, COALESCE(review_label, '') AS label, COUNT(*) AS n "
            f"FROM answer_log {where} {and_} feedback IS NOT NULL GROUP BY feedback, label"
        )
    return {
        "period": period if since else "",
        "totals": totals,
        "by_route": {r["route"]: r for r in by_route},
        "crosstab": {(r["route"], r["label"]): r["n"] for r in crosstab},
        "by_label": {r["label"]: r for r in by_label if r["label"] in REVIEW_LABELS},
        "by_model": by_model,
        "per_day": per_day,
        "errors": errors,
        "feedback": _feedback(feedback_by_route, feedback_crosstab),
    }
