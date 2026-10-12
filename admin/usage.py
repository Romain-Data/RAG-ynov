"""The usage of the chatbot on the dashboard (#16): the journal week by week
(journal/stats.py::weekly), the configurations it saw (config_changes) and the evaluation runs
of the preprod and the production placed on the same weeks.

The same definitions as the summary page: greetings apart, thumbs of the chat without the
greetings, questions without an answer of #20. A rate always comes with the count behind it;
a point computed on fewer than MIN_CASES questions or votes is drawn hollow. Every value read
from the journal (models, collections, versions) is escaped.
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape

from admin.charts import Mark, Point, Series, line_chart
from admin.dashboard import MONTHS
from admin.pages import _satisfaction
from eval import dashboard as figures
from journal.stats import WEEKS, week_start

MIN_CASES = 10  # below, a rate is drawn as a hollow point
BRIEF_WEEKS = 4
SERVER_ENVIRONMENTS = ("preprod", "prod")


def _day(date: str) -> str:
    """ "2026-10-05…" → "5 oct." (the text as it is when it is not a date)."""
    try:
        year, month, day = (int(part) for part in date[:10].split("-"))
        return f"{day} {MONTHS[month - 1]}"
    except (ValueError, IndexError):
        return date


def _rate(part: int, whole: int) -> str:
    """ "3/12 (25 %)", or "–" when there is nothing to divide."""
    return f"{part}/{whole} ({100 * part / whole:.0f} %)" if whole else "–"


def _number(value: float | None) -> str:
    return "–" if value is None else f"{value:,.0f}".replace(",", " ")


def _value(value: object) -> str:
    return str(value).replace(".", ",") if isinstance(value, float) else str(value)


def _questions(week: dict) -> int:
    return int(week["questions"]["chat"] + week["questions"]["api"])


def _nice_max(top: float, intervals: int = 4) -> float:
    """A round top for an axis of `intervals` steps (1, 2 or 5 times a power of ten)."""
    raw = max(top, 1) / intervals
    power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 2, 5, 10) if m * power >= raw)
    return float(step * intervals)


# --- What happened on which week --------------------------------------------------------------


def _week_index(weeks: list[dict], date: str) -> int | None:
    """The index of the week that contains `date` (ISO), None outside the weeks shown."""
    try:
        moment = datetime.fromisoformat(date[:10]).replace(tzinfo=UTC)
    except ValueError:
        return None
    start = week_start(moment).date().isoformat()
    return next((i for i, week in enumerate(weeks) if week["start"] == start), None)


@dataclass
class Events:
    """What happened during a week: evaluation runs on the servers, configuration changes."""

    runs: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)

    def text(self) -> str:
        parts = list(self.changes)
        if self.runs:
            parts.append(f"passage{'s' if len(self.runs) > 1 else ''} {', '.join(self.runs)}")
        return " ; ".join(parts)


def _run_text(run: dict) -> str:
    """ "10-09_02 (préprod) 24/24 correctes, 0 fausse": the Ynov questions answered right."""
    quality = figures.quality(run)
    name = figures.ENVIRONMENTS.get(run["environment"], run["environment"])
    wrong = f"{quality.wrong} fausse{'s' if quality.wrong > 1 else ''}"
    return (
        f"{figures.short_id(run)} ({name}) {quality.in_scope_ok}/{quality.in_scope_total} "
        f"correctes, {wrong}"
    )


def events(weeks: list[dict], changes: list[dict], runs: list[dict]) -> dict[int, Events]:
    """Per week index, what may explain a change of the figures: the evaluation runs of the
    preprod and the production, and the values of the configuration seen for the first time
    (the first value of each field is not a change)."""
    found: dict[int, Events] = {}
    for run in runs:
        if run["environment"] in SERVER_ENVIRONMENTS:
            index = _week_index(weeks, str(run["date"]))
            if index is not None:
                found.setdefault(index, Events()).runs.append(_run_text(run))
    for config in changes:
        for item in config["values"][1:]:
            index = _week_index(weeks, str(item["first"]))
            if index is not None:
                found.setdefault(index, Events()).changes.append(
                    f"{config['label']} : {_value(item['value'])} à partir du "
                    f"{_day(str(item['first']))}"
                )
    return dict(sorted(found.items()))


def _marks(weeks: list[dict], found: dict[int, Events]) -> tuple[list[Mark], str]:
    marks, items = [], []
    for number, (index, happened) in enumerate(found.items(), start=1):
        text = happened.text()
        label = f"semaine du {_day(weeks[index]['start'])}"
        marks.append(Mark(index, str(number), f"{label} : {text}"))
        items.append(f"<li>{escape(label)} : {escape(text)}</li>")
    listing = (
        '<p class="muted">Repères numérotés sur les graphiques, au début de la semaine '
        "concernée :</p>"
        f'<ol class="changes">{"".join(items)}</ol>'
        if items
        else ""
    )
    return marks, listing


# --- Brief --------------------------------------------------------------------------------------


def brief(weeks: list[dict]) -> str:
    """The card of « En bref »: the last four weeks of the journal."""
    title = f"<h3>Usage · {BRIEF_WEEKS} dernières semaines</h3>"
    last = weeks[-BRIEF_WEEKS:]
    if not last:
        return f'<div class="card">{title}<p class="big">0</p><p>Le journal est vide.</p></div>'
    chat = sum(w["questions"]["chat"] for w in last)
    api = sum(w["questions"]["api"] for w in last)
    reached = sum(w["gaps"]["questions"] for w in last)
    without = sum(w["gaps"]["without_answer"] for w in last)
    useful = sum(w["feedback"]["useful"] for w in last)
    rated = sum(w["feedback"]["rated"] for w in last)
    reviewed = sum(w["reviewed"] for w in last)
    return (
        f'<div class="card">{title}<p class="big">{chat + api}</p>'
        f"<p>questions depuis le {escape(_day(last[0]['start']))} (chat {chat} · API {api}, "
        "hors politesse)</p>"
        f"<p>Sans réponse : {escape(_rate(without, reached))}</p>"
        f"<p>Satisfaction : {escape(_satisfaction(useful, rated))}</p>"
        f'<p>{reviewed} revue(s) · <a href="#usage">détail par semaine</a></p></div>'
    )


# --- Section ------------------------------------------------------------------------------------


def _charts(weeks: list[dict], marks: list[Mark]) -> str:
    labels = [w["week"] for w in weeks]
    ticks = [(i, _day(w["start"])) for i, w in enumerate(weeks)]

    def label(week: dict) -> str:
        return f"semaine du {_day(week['start'])}"

    questions = line_chart(
        labels,
        [
            Series(
                "Chat",
                [
                    Point(w["questions"]["chat"], f"{label(w)} : {w['questions']['chat']}")
                    for w in weeks
                ],
                marker="circle",
                tone=0,
            ),
            Series(
                "API",
                [
                    Point(w["questions"]["api"], f"{label(w)} : {w['questions']['api']}")
                    for w in weeks
                ],
                marker="square",
                tone=2,
            ),
        ],
        title="Questions par semaine, hors politesse",
        y_max=_nice_max(max(max(w["questions"]["chat"], w["questions"]["api"]) for w in weeks)),
        y_format=lambda v: f"{v:.0f}",
        ticks=ticks,
        marks=marks,
        height=200,
    )

    def share(week: dict, part: int) -> Point:
        whole = week["gaps"]["questions"]
        if not whole:
            return Point(None)
        return Point(
            100 * part / whole,
            f"{label(week)} : {part}/{whole} questions",
            hollow=whole < MIN_CASES,
        )

    gaps = line_chart(
        labels,
        [
            Series(
                "Sans réponse",
                [share(w, w["gaps"]["without_answer"]) for w in weeks],
                marker="circle",
                tone=1,
                connect_gaps=False,
            ),
            Series(
                "dont refus au seuil",
                [share(w, w["gaps"]["by_kind"]["refus"]) for w in weeks],
                marker="diamond",
                tone=3,
                dashed=True,
                connect_gaps=False,
            ),
        ],
        title="Part des questions restées sans réponse, par semaine",
        y_max=100,
        y_format=lambda v: f"{v:.0f} %",
        ticks=ticks,
        marks=marks,
        height=200,
    )

    def satisfaction(week: dict) -> Point:
        rated, useful = week["feedback"]["rated"], week["feedback"]["useful"]
        if not rated:
            return Point(None)
        votes = f"{rated} vote{'s' if rated > 1 else ''}"
        return Point(
            100 * useful / rated,
            f"{label(week)} : {useful} « Utile » sur {votes}",
            hollow=rated < MIN_CASES,
        )

    thumbs = line_chart(
        labels,
        [
            Series(
                "Part d'« Utile »",
                [satisfaction(w) for w in weeks],
                marker="circle",
                tone=0,
                connect_gaps=False,
            )
        ],
        title="Satisfaction des utilisateurs du chat, par semaine",
        y_max=100,
        y_format=lambda v: f"{v:.0f} %",
        ticks=ticks,
        marks=marks,
        height=200,
    )
    return (
        "<h3>Questions par semaine</h3>"
        + questions
        + "<h3>Questions sans réponse</h3>"
        + gaps
        + "<h3>Satisfaction (pouces du chat, hors politesse)</h3>"
        + thumbs
    )


def _table(weeks: list[dict], found: dict[int, Events]) -> str:
    rows = []
    for index, w in enumerate(weeks):
        gaps, feedback = w["gaps"], w["feedback"]
        good = w["reviews"]["bonne"]
        reviews = (
            f"{w['reviewed']} ({good} bonne{'s' if good > 1 else ''})" if w["reviewed"] else "0"
        )
        latency = w["latency_ms_median"]
        duration = "–" if latency is None else f"{latency / 1000:.1f} s".replace(".", ",")
        tokens = (
            "–"
            if w["tokens_in_avg"] is None
            else f"{_number(w['tokens_in_avg'])} / {_number(w['tokens_out_avg'])}"
        )
        runs = found[index].runs if index in found else []
        numbers = [
            w["questions"]["chat"],
            w["questions"]["api"],
            w["smalltalk"],
            _rate(gaps["without_answer"], gaps["questions"]),
            gaps["by_kind"]["refus"],
            gaps["by_kind"]["incomplete"],
            w["errors"],
            _satisfaction(feedback["useful"], feedback["rated"]),
            reviews,
            duration,
            tokens,
        ]
        cells = "".join(f'<td class="num">{escape(str(n))}</td>' for n in numbers)
        rows.append(
            f"<tr><td>{escape(_day(w['start']))}</td>{cells}"
            f"<td>{escape(' ; '.join(runs))}</td></tr>"
        )
    return (
        '<div class="scroll"><table class="weeks"><thead><tr><th>Semaine du</th>'
        '<th class="num">Chat</th><th class="num">API</th><th class="num">Politesse</th>'
        '<th class="num">Sans réponse</th><th class="num">dont refus</th>'
        '<th class="num">Incomplètes</th><th class="num">Erreurs</th>'
        '<th class="num">Satisfaction</th><th class="num">Revues</th>'
        '<th class="num">Durée médiane</th><th class="num">Jetons (entrée / sortie)</th>'
        f"<th>Passages préprod et prod</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
        "</div>"
    )


def _changes_table(changes: list[dict]) -> str:
    rows = []
    for config in changes:
        values = config["values"]
        if not values:
            rows.append(
                f'<tr><td>{escape(config["label"])}</td><td class="muted">jamais renseigné</td>'
                '<td></td><td></td><td class="num">0</td></tr>'
            )
        for item in values:
            rows.append(
                f"<tr><td>{escape(config['label'])}</td><td>{escape(_value(item['value']))}</td>"
                f"<td>{escape(_day(str(item['first'])))}</td>"
                f"<td>{escape(_day(str(item['last'])))}</td>"
                f'<td class="num">{item["n"]}</td></tr>'
            )
    return (
        "<h3>Changements de configuration vus dans le journal</h3>"
        "<p class=\"muted\">Ce qui a répondu, d'après les entrées du journal, dans l'ordre "
        "d'apparition : un champ qui a deux valeurs ou plus a changé. Le modèle du LLM est celui "
        "que renvoie Mammouth (souvent l'alias, pas le modèle qui est derrière) ; les refus, la "
        "politesse et les erreurs n'en ont pas. La version reste vide tant que Coolify ne "
        "fournit pas <code>SOURCE_COMMIT</code> (option « Include Source Commit in Build » "
        "coupée).</p>"
        '<div class="scroll"><table><thead><tr><th>Champ</th><th>Valeur</th><th>Vu du</th>'
        '<th>au</th><th class="num">Entrées</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def section(weeks: list[dict], changes: list[dict], runs: list[dict]) -> str:
    """The section « Usage réel » of the dashboard."""
    title = '<h2 id="usage">Usage réel</h2>'
    since = f", depuis la semaine du {_day(weeks[0]['start'])}" if weeks else ""
    intro = (
        '<p class="muted">Ce que le journal des réponses dit de l\'usage, semaine par semaine '
        f"(du lundi au dimanche, UTC){escape(since)} ({WEEKS} semaines au plus), avec les "
        "définitions de la "
        '<a href="/admin/synthese">synthèse</a> : la politesse est mise à part, la satisfaction '
        "est la part d'« Utile » parmi les votes du chat hors politesse, les questions sans "
        'réponse sont celles de la page <a href="/admin/sans-reponse">Sans réponse</a>. Un taux '
        f"est toujours donné avec son effectif ; un point calculé sur moins de {MIN_CASES} "
        "questions ou votes est creux. Pour une période précise, les modèles, les scores face "
        'au seuil et les erreurs : la <a href="/admin/synthese">synthèse</a>.</p>'
    )
    if not weeks:
        return title + intro + '<p class="muted">Le journal est vide : aucune question.</p>'
    found = events(weeks, changes, runs)
    marks, listing = _marks(weeks, found)
    if len(weeks) < 2:
        charts = (
            '<p class="muted">Moins de deux semaines de données : les graphiques viendront avec '
            "la deuxième semaine, le tableau donne déjà les chiffres.</p>"
        )
    else:
        charts = _charts(weeks, marks) + listing
    return (
        title
        + intro
        + charts
        + "<h3>Semaine par semaine</h3>"
        + _table(weeks, found)
        + _changes_table(changes)
    )
