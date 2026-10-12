"""Inline SVG charts for the admin pages: no script and no library, since the CSP of /admin
forbids scripts (#16).

A chart draws series over the same labels: the x axis is their order (runs, weeks), not a
time scale. Each series has its own marker shape as well as its colour, each point a native
tooltip (`<title>`); a point can be hollow (a figure computed on few cases) or highlighted (a
milestone). Horizontal rules show a threshold, vertical marks a change between two points.
Every text is escaped. The chart is drawn in a 900-unit wide viewBox scaled to the width of
the page, at least 640 px: narrower, it scrolls inside its frame and the page does not.

The caller follows each chart with `data_table`, the same figures as text: exact values,
and what a screen reader reads.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html import escape

MARKERS = ("circle", "square", "diamond", "triangle", "none")
TONES = 4  # colour slots, see CHART_STYLE

_WIDTH = 900
_LEFT, _RIGHT, _TOP, _BOTTOM = 64, 24, 30, 34
_MAX_TICKS = 12

CHART_STYLE = """
.chart { overflow-x: auto; margin: .6rem 0 .2rem; }
.chart svg { display: block; width: 100%; min-width: 640px; height: auto; }
.chart text { font: 13px Inter, system-ui, sans-serif; fill: var(--muted); }
.chart .grid { stroke: var(--border); stroke-width: 1; }
.chart .rule { stroke: var(--error); stroke-width: 1.5; stroke-dasharray: 6 4; }
.chart text.rule-label { fill: var(--error); }
.chart .mark line { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 4; }
.chart .mark circle { fill: var(--soft); stroke: var(--muted); }
.chart .mark text { fill: var(--text); font-size: 11px; font-weight: 600; }
.chart .line { fill: none; stroke: var(--c); stroke-width: 2; }
.chart .line.dashed { stroke-dasharray: 7 5; }
.chart .pt, .legend .pt { fill: var(--c); stroke: var(--c); stroke-width: 1.5; }
.chart .pt.hollow, .legend .pt.hollow { fill: var(--card); }
.chart .pt.hl, .legend .pt.hl { stroke: var(--text); stroke-width: 2.5; }
.legend { display: flex; flex-wrap: wrap; gap: .2rem 1rem; margin: .2rem 0; padding: 0;
          list-style: none; font-size: .8rem; color: var(--muted); }
.legend li { display: flex; align-items: center; gap: .35rem; font-size: .8rem; }
.legend svg { width: 26px; height: 14px; }
.legend .line { fill: none; stroke: var(--c); stroke-width: 2; }
.legend .line.dashed { stroke-dasharray: 5 3; }
.t0 { --c: #325A38; } .t1 { --c: #a35c00; } .t2 { --c: #2f5d9e; } .t3 { --c: #8a3f8f; }
@media (prefers-color-scheme: dark) {
  .t0 { --c: #8fbf96; } .t1 { --c: #f0b45a; } .t2 { --c: #8db4ec; } .t3 { --c: #d9a3dd; }
}
details.data { margin: .2rem 0 1rem; }
details.data summary { cursor: pointer; font-size: .85rem; color: var(--accent); }
details.data .scroll { overflow-x: auto; }
details.data table { margin-top: .4rem; }
"""


@dataclass(frozen=True)
class Point:
    value: float | None  # None: no point at this label
    tip: str = ""  # the tooltip, plain text
    hollow: bool = False  # computed on few cases
    highlight: bool = False  # a milestone


@dataclass(frozen=True)
class Series:
    name: str
    points: Sequence[Point]  # one per label
    marker: str = "circle"  # one of MARKERS
    tone: int = 0  # colour slot, 0 to TONES - 1
    dashed: bool = False
    connect_gaps: bool = True  # join the points across the labels where it has no value


@dataclass(frozen=True)
class Rule:
    """A horizontal line: a threshold, a target."""

    value: float
    label: str


@dataclass(frozen=True)
class Mark:
    """A vertical line before a label: something changed there. `label` is drawn in a small
    badge at the top (a number, the caller lists what it stands for); `tip` is its tooltip."""

    index: int
    label: str
    tip: str = ""


def _plain(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _marker(shape: str, x: float, y: float, size: float, classes: str, tip: str) -> str:
    title = f"<title>{escape(tip)}</title>" if tip else ""
    if shape == "none":
        return ""
    if shape == "square":
        s = size * 0.9
        body = f'<rect x="{x - s:.1f}" y="{y - s:.1f}" width="{2 * s:.1f}" height="{2 * s:.1f}"'
    elif shape == "diamond":
        s = size * 1.25
        body = (
            f'<polygon points="{x:.1f},{y - s:.1f} {x + s:.1f},{y:.1f} '
            f'{x:.1f},{y + s:.1f} {x - s:.1f},{y:.1f}"'
        )
    elif shape == "triangle":
        s = size * 1.2
        body = (
            f'<polygon points="{x:.1f},{y - s:.1f} {x + s:.1f},{y + s * 0.8:.1f} '
            f'{x - s:.1f},{y + s * 0.8:.1f}"'
        )
    else:
        body = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}"'
    return f'{body} class="{classes}">{title}</{body.split()[0][1:]}>'


def _path(points: list[tuple[float, float] | None], connect_gaps: bool) -> str:
    """The `d` of a line through the points; a gap starts a new piece unless connected."""
    parts, move = [], True
    for point in points:
        if point is None:
            move = move or not connect_gaps
            continue
        parts.append(f"{'M' if move else 'L'}{point[0]:.1f},{point[1]:.1f}")
        move = False
    return " ".join(parts)


def line_chart(
    labels: Sequence[str],
    series: Sequence[Series],
    *,
    title: str,
    y_max: float,
    y_min: float = 0.0,
    y_format: Callable[[float], str] = _plain,
    y_ticks: int = 4,
    ticks: Sequence[tuple[int, str]] | None = None,
    rules: Sequence[Rule] = (),
    marks: Sequence[Mark] = (),
    height: int = 240,
) -> str:
    """An inline SVG line chart and its legend, as HTML.

    `labels` name the x positions, in order; every series has one point per label. The y axis
    goes from `y_min` to `y_max` with `y_ticks` intervals labelled by `y_format`. `ticks` are
    the x labels written under the axis, as (index, text); by default every label, thinned
    out to 12. `title` is what a screen reader announces."""
    count = len(labels)
    plot_w = _WIDTH - _LEFT - _RIGHT
    plot_h = height - _TOP - _BOTTOM
    span = (y_max - y_min) or 1.0

    def x_of(index: int) -> float:
        return _LEFT + (index + 0.5) * plot_w / max(count, 1)

    def y_of(value: float) -> float:
        ratio = min(max((value - y_min) / span, 0.0), 1.0)
        return _TOP + (1 - ratio) * plot_h

    out = [
        f'<svg viewBox="0 0 {_WIDTH} {height}" role="img" aria-label="{escape(title)}" '
        'xmlns="http://www.w3.org/2000/svg">',
        f"<title>{escape(title)}</title>",
    ]
    for step in range(y_ticks + 1):
        value = y_min + span * step / max(y_ticks, 1)
        y = y_of(value)
        out.append(
            f'<line class="grid" x1="{_LEFT}" x2="{_WIDTH - _RIGHT}" y1="{y:.1f}" y2="{y:.1f}"/>'
            f'<text x="{_LEFT - 8}" y="{y + 4:.1f}" text-anchor="end">'
            f"{escape(y_format(value))}</text>"
        )
    if ticks is None:
        every = max(1, math.ceil(count / _MAX_TICKS))
        ticks = [(i, label) for i, label in enumerate(labels) if i % every == 0]
    for index, text in ticks:
        if 0 <= index < count:
            out.append(
                f'<text x="{x_of(index):.1f}" y="{height - 10}" text-anchor="middle">'
                f"{escape(text)}</text>"
            )
    for rule in rules:
        y = y_of(rule.value)
        out.append(
            f'<line class="rule" x1="{_LEFT}" x2="{_WIDTH - _RIGHT}" y1="{y:.1f}" y2="{y:.1f}">'
            f"<title>{escape(rule.label)}</title></line>"
            f'<text class="rule-label" x="{_WIDTH - _RIGHT}" y="{y - 5:.1f}" '
            f'text-anchor="end">{escape(rule.label)}</text>'
        )
    for change in marks:
        if not 0 <= change.index < count:
            continue
        # Between the point and the one before: the change happened in between
        x = x_of(change.index) - plot_w / max(count, 1) / 2
        tip = f"<title>{escape(change.tip)}</title>" if change.tip else ""
        out.append(
            f'<g class="mark">{tip}<line x1="{x:.1f}" x2="{x:.1f}" y1="{_TOP - 6}" '
            f'y2="{_TOP + plot_h}"/><circle cx="{x:.1f}" cy="{_TOP - 14}" r="9"/>'
            f'<text x="{x:.1f}" y="{_TOP - 10}" text-anchor="middle">{escape(change.label)}'
            "</text></g>"
        )
    for item in series:
        tone = f"t{item.tone % TONES}"
        placed = [
            (x_of(i), y_of(p.value)) if p.value is not None else None
            for i, p in enumerate(item.points[:count])
        ]
        group = [f'<g class="series {tone}">']
        if d := _path(placed, item.connect_gaps):
            dashed = " dashed" if item.dashed else ""
            group.append(f'<path class="line{dashed}" d="{d}"/>')
        for point, xy in zip(item.points[:count], placed, strict=True):
            if xy is None:
                continue
            classes = (
                "pt" + (" hollow" if point.hollow else "") + (" hl" if point.highlight else "")
            )
            tip = f"{item.name} — {point.tip}" if point.tip else item.name
            group.append(
                _marker(item.marker, xy[0], xy[1], 6.5 if point.highlight else 4.5, classes, tip)
            )
        group.append("</g>")
        out.append("".join(group))
    out.append("</svg>")
    return f'<div class="chart">{"".join(out)}</div>{legend(series)}'


def _swatch(item: Series, classes: str = "pt") -> str:
    line = (
        f'<path class="line{" dashed" if item.dashed else ""}" d="M1,7 L25,7"/>'
        if item.marker == "none" or item.dashed
        else ""
    )
    return (
        f'<svg viewBox="0 0 26 14" aria-hidden="true" class="t{item.tone % TONES}">{line}'
        f"{_marker(item.marker, 13, 7, 4.5, classes, '')}</svg>"
    )


def legend(series: Sequence[Series]) -> str:
    """The names of the series with their marker, and what hollow and highlighted points
    mean when the chart has some."""
    items = [f"<li>{_swatch(item)}{escape(item.name)}</li>" for item in series]
    points = [p for item in series for p in item.points]
    sample = Series("", [], marker="circle", tone=0)
    if any(p.highlight for p in points if p.value is not None):
        items.append(f"<li>{_swatch(sample, 'pt hl')}étape clé</li>")
    if any(p.hollow for p in points if p.value is not None):
        items.append(f"<li>{_swatch(sample, 'pt hollow')}peu de cas</li>")
    return f'<ul class="legend">{"".join(items)}</ul>'


def data_table(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    summary: str = "Données du graphique",
    numeric: Sequence[int] = (),
) -> str:
    """The figures of a chart as a table, folded under `summary`. Cells are plain text;
    the columns of `numeric` are aligned right."""
    right = set(numeric)

    def cell(tag: str, index: int, text: str) -> str:
        cls = ' class="num"' if index in right else ""
        return f"<{tag}{cls}>{escape(text)}</{tag}>"

    head = "".join(cell("th", i, text) for i, text in enumerate(header))
    body = "".join(
        "<tr>" + "".join(cell("td", i, text) for i, text in enumerate(row)) + "</tr>"
        for row in rows
    )
    return (
        f'<details class="data"><summary>{escape(summary)}</summary><div class="scroll">'
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>"
    )
