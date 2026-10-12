"""The dashboard of /admin (#16): how the measured quality evolves, from the runs of
eval/results/ (eval/dashboard.py computes the figures, this module draws them).

Server-rendered like the other admin pages, without script: the charts are inline SVG
(admin/charts.py), each followed by its figures as a table. Every text that comes from a run
file (labels, review notes, models) is escaped.

The indicators of the journal (#18, #19, #20) come in through the `usage_brief` and `usage`
arguments of `dashboard_page`: HTML built by the caller, inserted as it is, a card in « En
bref » and a section after the measured quality.
"""

import math
from dataclasses import dataclass
from html import escape

from admin.charts import CHART_STYLE, Mark, Point, Series, data_table, line_chart
from admin.pages import layout
from eval import dashboard as figures

ENVIRONMENT_CHOICES = {"": "Tous", "local": "Local", "preprod": "Préprod", "prod": "Prod"}
MATRIX_CHOICES = {"e2e": "Bout en bout", "recherche": "Recherche"}
RUN_CHOICES = {"etapes": "Étapes clés", "tous": "Tous les passages"}
# Marker and colour slot of each environment, the same on every chart
ENVIRONMENT_STYLE = {"local": ("circle", 2), "preprod": ("diamond", 1), "prod": ("square", 0)}
MONTHS = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)
_TICK_GAP = 52  # viewBox units between two dates written under a chart

STYLE = """
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px;
         margin: .6rem 0 1rem; }
.card { border: 1px solid var(--border); border-radius: 10px; padding: .7rem .8rem;
        background: var(--soft); }
.card h3 { margin: 0 0 .2rem; font-size: .8rem; color: var(--muted); font-weight: 600; }
.card .big { font-size: 1.4rem; font-weight: 700; margin: 0; }
.card p { margin: .15rem 0; font-size: .85rem; }
.card dl { margin-top: .4rem; }
.card dt, .card dd { font-size: .78rem; }
h3 { font-size: .9rem; margin: 1.1rem 0 .2rem; }
.scroll { overflow-x: auto; }
.cases td:first-child, .cases td:nth-child(3) { white-space: nowrap; }
ol.changes { margin: .2rem 0 .6rem; padding-left: 1.4rem; }
ol.changes li { font-size: .82rem; }
.matrix { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px;
          margin: .5rem 0 .3rem; }
.matrix table { width: auto; min-width: 100%; }
.matrix th, .matrix td { white-space: nowrap; padding: .3rem .45rem; font-size: .8rem; }
.matrix thead th { text-align: center; vertical-align: bottom; }
.matrix th[scope=row], .matrix thead th:first-child { position: sticky; left: 0; z-index: 1;
          background: var(--card); text-align: left; font-weight: 400; color: var(--text); }
.matrix th[scope=row] { max-width: 17rem; overflow: hidden; text-overflow: ellipsis;
          border-right: 1px solid var(--border); }
.matrix td { text-align: center; }
.matrix tr.group th { background: var(--soft); color: var(--muted); font-weight: 600; }
.matrix small { color: var(--muted); font-weight: 400; }
.v-correct, .v-ok { background: rgba(50, 90, 56, .12); }
.v-partial { background: rgba(163, 92, 0, .14); }
.v-wrong, .v-ko, .v-error { background: rgba(179, 38, 30, .14); }
.v-refused, .v-no_answer { background: rgba(85, 96, 90, .14); }
@media (max-width: 640px) { .matrix th[scope=row] { max-width: 8rem; } }
"""


@dataclass(frozen=True)
class Filters:
    environment: str = ""  # "" for all, or a key of eval.dashboard.ENVIRONMENTS
    matrix: str = "e2e"  # a key of MATRIX_CHOICES
    runs: str = "etapes"  # a key of RUN_CHOICES

    @property
    def milestones_only(self) -> bool:
        return self.runs == "etapes"

    @property
    def matrix_kind(self) -> str:
        return "retrieval" if self.matrix == "recherche" else "e2e"


def parse_filters(environnement: str = "", matrice: str = "", passages: str = "") -> Filters:
    """The filters of the query string; an unknown value falls back to the default."""
    return Filters(
        environnement if environnement in figures.ENVIRONMENTS else "",
        matrice if matrice in MATRIX_CHOICES else "e2e",
        passages if passages in RUN_CHOICES else "etapes",
    )


# --- Formatting ---------------------------------------------------------------------------------


def _fr(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _signed(value: float) -> str:
    return ("+" if value >= 0 else "−") + _fr(abs(value), 3)


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f} %" if whole else "–"


def _day(date: str) -> str:
    """ "2026-10-02" → "2 oct." (the date as it is when it is not one)."""
    try:
        year, month, day = (int(part) for part in date.split("-"))
        return f"{day} {MONTHS[month - 1]}"
    except (ValueError, IndexError):
        return date


def _env(run: dict) -> str:
    return figures.ENVIRONMENTS.get(run["environment"], str(run["environment"]))


def _embedding(run: dict) -> str:
    """The short name of the embedding model of a run ("paraphrase-multilingual-MiniLM…")."""
    return str((run.get("config") or {}).get("embedding_model") or "?").split("/")[-1]


def _threshold(run: dict) -> str:
    value = figures.threshold(run)
    return "inconnu" if value is None else _fr(value)


def _known(run: dict, key: str, value: str | None, unknown: str) -> str:
    """A value of the configuration of a run, saying when it was reconstructed afterwards."""
    if value is None:
        return unknown
    return f"{value} (reconstitué)" if figures.reconstructed(run, key) else value


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _day_ticks(runs: list[dict]) -> list[tuple[int, str]]:
    """The date under the first run of each day, skipped when too close to the previous one."""
    unit = 812 / max(len(runs), 1)  # width of the plot divided by the number of runs
    ticks: list[tuple[int, str]] = []
    previous = ""
    for index, run in enumerate(runs):
        if run["date"] == previous:
            continue
        previous = run["date"]
        if ticks and (index - ticks[-1][0]) * unit < _TICK_GAP:
            continue
        ticks.append((index, _day(run["date"])))
    return ticks


def _marks(runs: list[dict]) -> tuple[list[Mark], str]:
    """The changes between the runs shown (eval/dashboard.py::changes): numbered marks on
    the chart, and the list of what each number stands for."""
    found = figures.changes(runs)
    marks: list[Mark] = []
    items: list[str] = []
    for index, run in enumerate(runs):
        lines = found.get(run["run_id"])
        if not lines:
            continue
        number = str(len(marks) + 1)
        text = " ; ".join(lines)
        marks.append(Mark(index, number, f"{figures.short_id(run)} ({_env(run)}) : {text}"))
        items.append(
            f"<li><code>{escape(figures.short_id(run))}</code> ({escape(_env(run))}) : "
            f"{escape(text)}</li>"
        )
    listing = (
        '<p class="muted">Changements marqués sur les graphiques (depuis le passage précédent '
        "du même environnement) :</p>"
        f'<ol class="changes">{"".join(items)}</ol>'
        if items
        else ""
    )
    return marks, listing


def _per_environment(
    runs: list[dict], value: list[float | None], tips: list[str], suffix: str = ""
) -> list[Series]:
    """One series per environment over the same runs: a run of another environment is a gap,
    joined so that each environment reads as one line."""
    present = [e for e in figures.ENVIRONMENTS if any(r["environment"] == e for r in runs)]
    present += sorted({r["environment"] for r in runs} - set(present))
    series = []
    for environment in present:
        marker, tone = ENVIRONMENT_STYLE.get(environment, ("triangle", 3))
        points = [
            Point(v, tip, highlight=bool(run.get("milestone")))
            if run["environment"] == environment
            else Point(None)
            for run, v, tip in zip(runs, value, tips, strict=True)
        ]
        name = figures.ENVIRONMENTS.get(environment, environment)
        series.append(Series(f"{name}{suffix}", points, marker=marker, tone=tone))
    return series


def _filters_form(filters: Filters) -> str:
    def select(name: str, label: str, choices: dict[str, str], value: str) -> str:
        options = "".join(
            f'<option value="{escape(key)}"{" selected" if key == value else ""}>'
            f"{escape(text)}</option>"
            for key, text in choices.items()
        )
        return f'<label>{escape(label)}<select name="{name}">{options}</select></label>'

    return (
        '<form class="filters" method="get" action="/admin/tableau-de-bord">'
        + select("environnement", "Environnement", ENVIRONMENT_CHOICES, filters.environment)
        + select("matrice", "Matrice", MATRIX_CHOICES, filters.matrix)
        + select("passages", "Passages", RUN_CHOICES, filters.runs)
        + "<button>Afficher</button></form>"
    )


# --- Sections -----------------------------------------------------------------------------------


def _run_card(title: str, run: dict) -> str:
    quality = figures.quality(run)
    out_scope = (
        f" · {quality.out_of_scope_ok}/{quality.out_of_scope_total} hors sujet écartées"
        if quality.out_of_scope_total
        else ""
    )
    details = [
        ("Passage", figures.short_id(run)),
        ("Date", _day(run["date"])),
        ("Modèle", _known(run, "llm_model", figures.model(run), "inconnu")),
        ("Collection", _known(run, "collection", figures.collection(run), "inconnue")),
        ("Version", _known(run, "server_version", figures.version(run), "inconnue")),
    ]
    rows = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in details)
    return (
        f'<div class="card"><h3>{escape(title)}</h3>'
        f'<p class="big">{quality.in_scope_ok}/{quality.in_scope_total}</p>'
        f"<p>questions Ynov correctes{escape(out_scope)} · "
        f"{escape(_plural(quality.wrong, 'fausse', 'fausses'))}</p><dl>{rows}</dl></div>"
    )


def _retrieval_card(run: dict) -> str:
    quality = figures.quality(run)
    found = figures.margins(run)
    lines = [f"<p>questions Ynov retrouvées · {escape(_day(run['date']))}</p>"]
    if found and found.threshold is not None:
        lines.append(
            f"<p>Seuil {_fr(found.threshold)} : question Ynov la plus faible "
            f"{_fr(found.in_scope_min, 3)} ({_signed(found.in_scope_min - found.threshold)}), "
            f"hors sujet la plus forte {_fr(found.out_of_scope_max, 3)} "
            f"({_signed(found.threshold - found.out_of_scope_max)})</p>"
        )
    return (
        '<div class="card"><h3>Recherche · dernier passage</h3>'
        f'<p class="big">{quality.in_scope_ok}/{quality.in_scope_total}</p>{"".join(lines)}'
        "</div>"
    )


def _cases_card(cases: list[dict]) -> str:
    counts = figures.edge_case_counts(cases)
    still = [str(c["id"]) for c in cases if c.get("status") in ("open", "mitigated")]
    return (
        '<div class="card"><h3>Cas limites</h3>'
        f'<p class="big">{len(still)}</p>'
        f"<p>ouvert(s) ou atténué(s){escape(' : ' + ', '.join(still) if still else '')}</p>"
        f"<p>{counts.get('fixed', 0)} corrigé(s) sur {len(cases)}</p></div>"
    )


def _brief(data: figures.Data, usage_brief: str) -> str:
    cards = []
    for environment, name in figures.ENVIRONMENTS.items():
        if (run := figures.latest(data.runs, "e2e", environment)) is not None:
            cards.append(_run_card(f"Bout en bout · {name}", run))
    if (run := figures.latest(data.runs, "retrieval")) is not None:
        cards.append(_retrieval_card(run))
    cards.append(_cases_card(data.edge_cases))
    return f'<h2>En bref</h2><div class="cards">{"".join(cards)}{usage_brief}</div>'


def _e2e_section(runs: list[dict], filters: Filters) -> str:
    title = "<h2>Qualité de bout en bout dans le temps</h2>"
    chosen = figures.select(runs, "e2e", filters.environment)
    if not chosen:
        return title + '<p class="muted">Aucun passage de bout en bout ici.</p>'
    labels = [figures.short_id(run) for run in chosen]
    qualities = [figures.quality(run) for run in chosen]
    tips = [
        f"{figures.short_id(run)} · {_day(run['date'])} · {q.in_scope_ok}/{q.in_scope_total} "
        f"questions Ynov · {_plural(q.wrong, 'fausse', 'fausses')} · jeu "
        f"{run.get('question_set', '?')} · {figures.model(run) or 'modèle inconnu'}"
        for run, q in zip(chosen, qualities, strict=True)
    ]
    ticks = _day_ticks(chosen)
    marks, listing = _marks(chosen)
    share = line_chart(
        labels,
        _per_environment(
            chosen,
            [
                100 * q.in_scope_ok / q.in_scope_total if q.in_scope_total else None
                for q in qualities
            ],
            tips,
        ),
        title="Part des questions Ynov correctes, par passage",
        y_max=100,
        y_format=lambda v: f"{v:.0f} %",
        ticks=ticks,
        marks=marks,
    )
    reference = line_chart(
        labels,
        _per_environment(
            chosen,
            [None if q.reference_ok is None else float(q.reference_ok) for q in qualities],
            tips,
        ),
        title="Questions de référence q01 à q16 correctes, par passage",
        y_max=16,
        ticks=ticks,
        marks=marks,
        height=200,
    )
    top = max([2, *(q.wrong for q in qualities)])
    wrong = line_chart(
        labels,
        _per_environment(chosen, [float(q.wrong) for q in qualities], tips),
        title="Réponses fausses, par passage",
        y_max=top,
        y_ticks=top if top <= 8 else 4,
        ticks=ticks,
        marks=marks,
        height=170,
    )
    rows = []
    for run, q in zip(chosen, qualities, strict=True):
        latency = figures.median_latency(run)
        rows.append(
            [
                figures.short_id(run),
                _day(run["date"]),
                _env(run),
                str(run.get("question_set", "")),
                _known(run, "llm_model", figures.model(run), "inconnu"),
                _known(run, "collection", figures.collection(run), "inconnue"),
                f"{q.in_scope_ok}/{q.in_scope_total}",
                f"{q.out_of_scope_ok}/{q.out_of_scope_total}" if q.out_of_scope_total else "–",
                str(q.wrong),
                "–" if q.reference_ok is None else f"{q.reference_ok}/16",
                "–" if latency is None else f"{_fr(latency, 1)} s",
                "oui" if run.get("milestone") else "",
                str(run.get("label", "")),
            ]
        )
    table = data_table(
        [
            "Passage",
            "Date",
            "Env.",
            "Jeu",
            "Modèle",
            "Collection",
            "Questions Ynov",
            "Hors sujet",
            "Fausses",
            "q01–q16",
            "Durée médiane",
            "Étape clé",
            "Libellé",
        ],
        rows,
        summary="Les passages de bout en bout en chiffres",
        numeric=(6, 7, 8, 9, 10),
    )
    return (
        title + '<p class="muted">Verdicts relus à la main. Le nombre de questions change avec le '
        "jeu (16, 22, 24…) : les 16 questions de référence, posées depuis le 2 octobre, sont "
        "la seule courbe comparable d'un bout à l'autre. Les passages locaux n'ont pas "
        "toujours le même LLM que la préprod et la prod (voir le modèle de chaque point).</p>"
        + "<h3>Questions Ynov correctes</h3>"
        + share
        + "<h3>Les 16 questions de référence (q01 à q16)</h3>"
        + reference
        + "<h3>Réponses fausses</h3>"
        + wrong
        + listing
        + table
    )


def _retrieval_section(runs: list[dict], filters: Filters) -> str:
    title = "<h2>Recherche</h2>"
    chosen = figures.select(runs, "retrieval", filters.environment, filters.milestones_only)
    if not chosen:
        return title + '<p class="muted">Aucun passage de recherche ici.</p>'
    labels = [figures.short_id(run) for run in chosen]
    qualities = [figures.quality(run) for run in chosen]
    ticks = _day_ticks(chosen)
    marks, listing = _marks(chosen)
    scope = "les étapes clés" if filters.milestones_only else "tous les passages"
    tips = [
        f"{figures.short_id(run)} · {_day(run['date'])} · {run.get('label', '')} · "
        f"{_embedding(run)}, seuil {_threshold(run)}"
        for run in chosen
    ]
    found = line_chart(
        labels,
        [
            Series(
                "Questions Ynov retrouvées",
                [
                    Point(
                        100 * q.in_scope_ok / q.in_scope_total if q.in_scope_total else None,
                        f"{q.in_scope_ok}/{q.in_scope_total} · {tip}",
                        highlight=bool(run.get("milestone")),
                    )
                    for run, q, tip in zip(chosen, qualities, tips, strict=True)
                ],
                marker="circle",
                tone=2,
            ),
            Series(
                "Questions hors sujet refusées",
                [
                    Point(
                        100 * q.out_of_scope_ok / q.out_of_scope_total
                        if q.out_of_scope_total
                        else None,
                        f"{q.out_of_scope_ok}/{q.out_of_scope_total} · {tip}",
                        highlight=bool(run.get("milestone")),
                    )
                    for run, q, tip in zip(chosen, qualities, tips, strict=True)
                ],
                marker="diamond",
                tone=1,
            ),
        ],
        title="Part des questions retrouvées par la recherche, par passage",
        y_max=100,
        y_format=lambda v: f"{v:.0f} %",
        ticks=ticks,
        marks=marks,
    )
    return (
        title + f'<p class="muted">Recherche seule, sans LLM, en local ({scope}) : une question '
        "Ynov passe quand la bonne section ou le fait attendu atteint le contexte, une "
        "question hors sujet quand le seuil la refuse.</p>" + found + listing + _margins(chosen)
    )


def _margins(runs: list[dict]) -> str:
    """The extreme scores against the threshold, for the embedding model of the last run that
    measured them; the other models score on another scale and stay in the table."""
    measured = [(run, m) for run in runs if (m := figures.margins(run)) is not None]
    if not measured:
        return ""
    model = (measured[-1][0].get("config") or {}).get("embedding_model")
    same = [
        (run, m) for run, m in measured if (run.get("config") or {}).get("embedding_model") == model
    ]
    values = [v for _, m in same for v in (m.in_scope_min, m.out_of_scope_max, m.threshold) if v]
    # Round bounds a little beyond the values, on a step that gives at most 8 intervals
    step = 0.01 if max(values) - min(values) <= 0.06 else 0.02
    low = math.floor(min(values) / step - 1) * step
    high = math.ceil(max(values) / step + 1) * step

    def tip(run: dict, m: figures.Margins) -> str:
        threshold = "inconnu" if m.threshold is None else _fr(m.threshold)
        return (
            f"{figures.short_id(run)} · Ynov la plus faible {_fr(m.in_scope_min, 3)} · hors "
            f"sujet la plus forte {_fr(m.out_of_scope_max, 3)} · seuil {threshold}"
        )

    labels = [figures.short_id(run) for run, _ in same]
    chart = line_chart(
        labels,
        [
            Series(
                "Question Ynov la plus faible",
                [
                    Point(m.in_scope_min, tip(r, m), highlight=bool(r.get("milestone")))
                    for r, m in same
                ],
                marker="circle",
                tone=0,
            ),
            Series(
                "Question hors sujet la plus forte",
                [
                    Point(m.out_of_scope_max, tip(r, m), highlight=bool(r.get("milestone")))
                    for r, m in same
                ],
                marker="diamond",
                tone=1,
            ),
            Series(
                "Seuil",
                [Point(m.threshold, tip(r, m)) for r, m in same],
                marker="none",
                tone=3,
                dashed=True,
            ),
        ],
        title="Scores extrêmes de la recherche face au seuil, par passage",
        y_min=low,
        y_max=high,
        y_format=lambda v: _fr(v),
        y_ticks=round((high - low) / step),
        ticks=_day_ticks([run for run, _ in same]),
        height=220,
    )
    rows = [
        [
            figures.short_id(run),
            _day(run["date"]),
            _embedding(run),
            _fr(m.in_scope_min, 3),
            _fr(m.out_of_scope_max, 3),
            _signed(m.gap),
            "–" if m.threshold is None else _fr(m.threshold),
        ]
        for run, m in measured
    ]
    table = data_table(
        [
            "Passage",
            "Date",
            "Modèle d'embedding",
            "Ynov la plus faible",
            "Hors sujet la plus forte",
            "Écart",
            "Seuil",
        ],
        rows,
        summary="Les scores extrêmes de chaque passage (tous modèles)",
        numeric=(3, 4, 5, 6),
    )
    name = str(model or "?").split("/")[-1]
    return (
        "<h3>Le seuil et ses marges</h3>"
        f'<p class="muted">Modèle {escape(name)}. Le seuil doit rester entre les deux '
        "courbes : au-dessus de la question hors sujet la plus forte, au-dessous de la question "
        "Ynov la plus faible. Un écart négatif veut dire qu'aucun seuil ne les sépare. Les "
        "autres modèles d'embedding, sur une autre échelle de scores, sont dans le tableau.</p>"
        + chart
        + table
    )


def _matrix_section(data: figures.Data, filters: Filters) -> str:
    kind = filters.matrix_kind
    runs = figures.select(data.runs, kind, filters.environment, filters.milestones_only)
    title = "<h2>Matrice question × passage</h2>"
    if not runs:
        return title + '<p class="muted">Aucun passage à afficher avec ces filtres.</p>'
    rows = [
        row
        for row in figures.matrix(runs, data.questions, data.edge_cases)
        if any(cell.state != "absent" for cell in row.cells)
    ]
    head = "".join(
        f'<th title="{escape(str(run.get("label", "")))}">{escape(figures.short_id(run))}'
        f"<br><small>{escape(_env(run))}</small></th>"
        for run in runs
    )
    body = []
    group = None
    for row in rows:
        if row.out_of_scope != group:
            group = row.out_of_scope
            name = "Questions hors sujet" if group else "Questions Ynov"
            body.append(
                f'<tr class="group"><th scope="row">{name}</th><td colspan="{len(runs)}"></td></tr>'
            )
        cases = f" <small>{escape(', '.join(row.edge_cases))}</small>" if row.edge_cases else ""
        cells = "".join(
            f'<td class="v-{escape(cell.state)}" title="{escape(cell.tip)}">'
            f"{escape(cell.text)}</td>"
            for cell in row.cells
        )
        body.append(
            f'<tr><th scope="row" title="{escape(row.question)}"><strong>'
            f"{escape(row.question_id)}</strong> {escape(row.question)}{cases}</th>{cells}</tr>"
        )
    if kind == "e2e":
        legend = " · ".join(
            f"{icon} {figures.VERDICT_LABELS[verdict]}"
            for verdict, icon in figures.VERDICT_ICONS.items()
        )
    else:
        legend = (
            "✅ n : bonne section au rang n · ✅ ctx : fait attendu dans le contexte · ❌ : "
            "absente · (d/m) : sections distinctes / requises · ⛔ : refusée par le seuil"
        )
    columns = "".join(
        f"<li><code>{escape(figures.short_id(run))}</code> ({escape(_env(run))}) : "
        f"{escape(str(run.get('label', '')))}</li>"
        for run in runs
    )
    return (
        title + f'<p class="muted">{escape(MATRIX_CHOICES[filters.matrix])}, '
        f"{escape(RUN_CHOICES[filters.runs].lower())} ({len(runs)}). {escape(legend)} · "
        "· : question absente du passage. Survoler une case pour le verdict et la note de "
        "revue.</p>"
        + '<div class="matrix"><table><thead><tr><th>Question</th>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
        + f'<details class="data"><summary>Les colonnes</summary><ul>{columns}</ul></details>'
    )


def _cases_section(cases: list[dict]) -> str:
    title = "<h2>Cas limites</h2>"
    if not cases:
        return title + '<p class="muted">Aucun cas limite lisible.</p>'
    counts = figures.edge_case_counts(cases)
    tags = " ".join(
        f'<span class="tag">{escape(figures.STATUS_LABELS.get(status, status))} : {n}</span>'
        for status, n in counts.items()
        if n
    )
    order = {status: i for i, status in enumerate(figures.STATUS_LABELS)}
    rows = "".join(
        f"<tr><td>{escape(str(c['id']))}</td><td>{escape(str(c.get('title', '')))}</td>"
        f"<td>{escape(figures.STATUS_LABELS.get(str(c.get('status')), str(c.get('status'))))}"
        f"</td><td>{escape(str(c.get('category', '')))}</td>"
        f"<td>{escape(', '.join(str(q) for q in c.get('questions') or []))}</td>"
        f"<td>{escape(str(c.get('discovered_in') or '—'))}</td></tr>"
        for c in sorted(cases, key=lambda c: order.get(str(c.get("status")), len(order)))
    )
    return (
        title
        + f"<p>{tags}</p>"
        + '<div class="scroll"><table class="cases"><thead><tr><th>Id</th><th>Titre</th>'
        "<th>Statut</th><th>Catégorie</th><th>Questions</th><th>Découvert dans</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def _agreement_section(runs: list[dict]) -> str:
    found = figures.auto_check_agreement(runs)
    title = "<h2>Fiabilité de la vérification automatique</h2>"
    if not found.reviewed:
        return title + '<p class="muted">Aucune réponse relue.</p>'
    rows = [
        [
            run_id[5:13],
            question_id,
            figures.VERDICT_LABELS.get(verdict, verdict),
            figures.VERDICT_LABELS.get(automatic, automatic),
        ]
        for run_id, question_id, verdict, automatic in found.disagreements
    ]
    return (
        title + f"<p>Sur {found.reviewed} réponses relues à la main, la vérification automatique "
        f"(<code>answer_must</code>) donne le même verdict dans {found.agree} cas "
        f"({_pct(found.agree, found.reviewed)}) : elle se trompe dans les deux sens, d'où la "
        "relecture de chaque passage.</p>"
        + data_table(
            ["Passage", "Question", "Revue", "Automatique"],
            rows,
            summary=f"Les {len(rows)} désaccords",
        )
    )


def dashboard_page(
    data: figures.Data, filters: Filters, *, usage_brief: str = "", usage: str = ""
) -> str:
    """The dashboard: in brief, the end-to-end quality and the retrieval over time, the
    question × run matrix, the edge cases and how reliable the automatic check is.

    `usage_brief` is a card added to « En bref » and `usage` a section added after the
    measured quality: the indicators of the journal, as HTML (escaped by their author)."""
    runs = data.runs
    if runs:
        intro = (
            f"<p>{len(runs)} passages d'évaluation enregistrés, du {escape(_day(runs[0]['date']))} "
            f"au {escape(_day(runs[-1]['date']))}, lus dans <code>eval/results/</code>. Un "
            "nouveau passage apparaît ici après le déploiement de la PR qui l'enregistre ; la vue "
            "texte est dans <code>eval/REPORT.md</code>.</p>"
        )
    else:
        intro = '<p class="muted">Aucun passage d\'évaluation lisible.</p>'
    problems = (
        "<h2>Fichiers écartés</h2>"
        + "<ul>"
        + "".join(f"<li>{escape(problem)}</li>" for problem in data.problems)
        + "</ul>"
        if data.problems
        else ""
    )
    body = (
        intro
        + _brief(data, usage_brief)
        + '<h2 class="sr">Filtres</h2>'
        + '<p class="muted">Les filtres valent pour les graphiques et la matrice.</p>'
        + _filters_form(filters)
        + _e2e_section(runs, filters)
        + _retrieval_section(runs, filters)
        + _matrix_section(data, filters)
        + _cases_section(data.edge_cases)
        + _agreement_section(runs)
        + usage
        + problems
    )
    return layout("Tableau de bord", body, style=CHART_STYLE + STYLE)
