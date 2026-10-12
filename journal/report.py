"""The monthly report of the questions left without an answer (#20): what the visitors looked
for in a calendar month (UTC) and did not find, by theme, next to the month before.

Read-only, and computed on demand from the journal (/admin/rapport): the detection is the one
of journal/gaps.py, the themes and their causes the ones decided in /admin/sans-reponse. A month
can be computed while its questions are in the journal (ANSWER_LOG_RETENTION_DAYS, 6 months):
the downloaded file is the archive.

    python -m journal.report --mois 2026-10 --out rapport.html

reads the database of CHAT_DB_PATH: a local copy of a backup, never the copies of the backup
folder themselves (opening them creates -wal/-shm files that the rotation never deletes).
"""

import argparse
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from chat.db import db, init_db
from journal.stats import gaps_between
from journal.themes import list_themes, unthemed

MONTH_NAMES = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip
# Examples are quoted only for a theme raised in at least this many conversations in the month:
# a question asked once may tell who asked it.
QUOTE_FROM = 2
OFF_TOPIC_SHOWN = 5
# The sections of the report, by cause of the theme (journal/themes.py::CAUSES); None = not
# decided yet ("à vérifier")
SECTIONS = {
    "contenu": "missing",
    None: "to_check",
    "recherche": "search",
    "hors_sujet": "off_topic",
}
_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def parse_month(raw: str | None) -> str:
    """`raw` when it is a month AAAA-MM, else the current month (never an error)."""
    match = _MONTH.match((raw or "").strip())
    if match and 2000 <= int(match.group(1)) <= 2999:
        return match.group(0)
    return current_month()


def previous_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:])
    return f"{year - 1}-12" if number == 1 else f"{year}-{number - 1:02d}"


def _next_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:])
    return f"{year + 1}-01" if number == 12 else f"{year}-{number + 1:02d}"


def bounds(month: str) -> tuple[str, str]:
    """The ISO dates that bound the month: its first day (included), the next one (excluded).
    Dates without a time compare right with the stored ones ("2026-10-01" < "2026-10-01T…")."""
    return f"{month}-01", f"{_next_month(month)}-01"


def month_label(month: str) -> str:
    return f"{MONTH_NAMES[int(month[5:]) - 1]} {month[:4]}"


def available_months(selected: str | None = None) -> list[str]:
    """The months of the journal, newest first, with the current month and `selected`."""
    with db() as conn:
        found = {
            month
            for (month,) in conn.execute("SELECT DISTINCT substr(created_at, 1, 7) FROM answer_log")
            if month and _MONTH.match(month)
        }
    found |= {current_month(), *([selected] if selected else [])}
    return sorted(found, reverse=True)


def trend(now: int, before: int) -> str:
    """The theme next to the month before: nouveau, en hausse, stable, en baisse."""
    if not before:
        return "nouveau"
    if now > before:
        return "en hausse"
    return "stable" if now == before else "en baisse"


def month_report(month: str) -> dict:
    """Everything the report of `month` (AAAA-MM, already valid) shows."""
    start, end = bounds(month)
    previous = previous_month(month)
    before_start, before_end = bounds(previous)
    before = {t["id"]: t["questions"] for t in list_themes(start=before_start, end=before_end)}
    sections: dict[str, list[dict]] = {name: [] for name in SECTIONS.values()}
    for theme in list_themes(start=start, end=end):
        quoted = theme["conversations"] >= QUOTE_FROM
        sections[SECTIONS.get(theme["cause"], "to_check")].append(
            {
                **theme,
                "previous": before.get(theme["id"], 0),
                "trend": trend(theme["questions"], before.get(theme["id"], 0)),
                "quoted": quoted,
                "examples": theme["examples"] if quoted else [],
            }
        )
    off_topic = sections["off_topic"]
    return {
        "month": month,
        "label": month_label(month),
        "previous_label": month_label(previous),
        "counts": gaps_between(start, end),
        "previous_counts": gaps_between(before_start, before_end),
        "unthemed": unthemed(start=start, end=end)[0],
        **sections,
        "off_topic_total": sum(t["questions"] for t in off_topic),
        "off_topic": off_topic[:OFF_TOPIC_SHOWN],
        "generated_at": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write the monthly report of the questions left without an answer (#20)."
    )
    parser.add_argument("--mois", default="", help="AAAA-MM (default: the current month)")
    parser.add_argument("--out", required=True, type=Path, help="HTML file to write")
    args = parser.parse_args()
    from admin.pages import report_document  # the HTML lives with the other admin pages

    init_db()  # an older copy gets the columns of the themes
    month = parse_month(args.mois)
    try:
        html = report_document(month_report(month))
    except sqlite3.Error as exc:
        raise SystemExit(f"The journal could not be read: {exc}") from exc
    args.out.write_text(html, encoding="utf-8")
    print(f"Report of {month} written to {args.out}")


if __name__ == "__main__":
    main()
