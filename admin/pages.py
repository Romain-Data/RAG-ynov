"""HTML of the admin pages. Server-rendered, no JavaScript (the CSP forbids scripts).

Everything that comes from the journal (a question typed by a stranger, an answer from the
LLM, a URL from the index) goes through `escape`; the answer is shown as preformatted text,
never as Markdown.
"""

from datetime import datetime
from html import escape
from urllib.parse import urlencode

from chat.pages import APP_NAME
from journal.gaps import GAP_KINDS, WITHOUT_ANSWER
from journal.review import PAGE_SIZE, REVIEW_LABELS
from journal.themes import BATCH_SIZE, CAUSES, MAX_NAME, MAX_NOTE

LABELS = {
    "bonne": "Bonne",
    "partielle": "Partielle",
    "fausse": "Fausse",
    "hors_sujet": "Hors sujet",
}
ROUTES = {
    "generate": "Générée",
    "refuse": "Refus au seuil",
    "smalltalk": "Politesse",
    "error": "Erreur",
}
CHANNELS = {"chat": "Chat", "api": "API"}
# The users' thumbs (#19): the value of the journal, the words of the chat, the icon shown
FEEDBACK = {1: ("Utile", "👍"), 0: ("Pas utile", "👎")}
FEEDBACK_CHOICES = {"positif": "Utile", "negatif": "Pas utile", "sans": "Sans avis (chat)"}
# The questions left without an answer (#20, journal/gaps.py)
GAP_CHOICES = {"tous": "Tous genres confondus", "aucune": "Sans aucune réponse", **GAP_KINDS}

_STYLE = """
:root { color-scheme: light dark; --accent: #325A38; --bg: #EAF0EB; --card: #fff;
        --text: #141a14; --muted: #55605a; --border: #cfd9d1; --error: #b3261e;
        --soft: #f3f6f3; }
@media (prefers-color-scheme: dark) {
  :root { --accent: #8fbf96; --bg: #121613; --card: #1b211c; --text: #e7ece8;
          --muted: #a3aea6; --border: #2e382f; --error: #f2a29b; --soft: #232b24; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; font-family: Inter, system-ui, sans-serif;
       background: var(--bg); color: var(--text); }
main { max-width: 1000px; margin: 0 auto; background: var(--card); padding: 24px;
       border: 1px solid var(--border); border-radius: 12px; }
header { display: flex; justify-content: space-between; align-items: center; gap: 12px;
         flex-wrap: wrap; margin-bottom: 1rem; }
h1 { font-size: 1.3rem; margin: 0; }
h2 { font-size: 1rem; margin: 1.5rem 0 .4rem; }
p, li, td, th, label { font-size: .9rem; line-height: 1.5; }
.muted { color: var(--muted); }
a { color: var(--accent); }
form.inline { display: inline; }
form.filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; margin-bottom: 1rem; }
form.filters label { display: flex; flex-direction: column; gap: 2px; font-size: .8rem; }
input[type=text], input[type=password], select, textarea { padding: .45rem .55rem; font: inherit;
       border: 1px solid var(--border); border-radius: 8px; background: transparent;
       color: inherit; }
textarea { width: 100%; min-height: 4.5rem; }
button, .button { padding: .5rem .9rem; border: 0; border-radius: 8px; background: var(--accent);
       color: var(--card); font: inherit; cursor: pointer; text-decoration: none; }
button.link { background: transparent; color: var(--accent); padding: 0;
              text-decoration: underline; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: .45rem .5rem; border-bottom: 1px solid var(--border);
         vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: .8rem; }
td.num { text-align: right; white-space: nowrap; }
.tag { display: inline-block; padding: 0 .5rem; border-radius: 999px; background: var(--soft);
       border: 1px solid var(--border); font-size: .8rem; white-space: nowrap; }
.error { color: var(--error); font-weight: 600; }
pre { white-space: pre-wrap; word-break: break-word; background: var(--soft); padding: .8rem;
      border-radius: 8px; border: 1px solid var(--border); font: .9rem/1.5 ui-monospace, monospace;
      margin: 0; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: .2rem 1rem; margin: 0; }
dt { color: var(--muted); font-size: .85rem; }
dd { margin: 0; font-size: .9rem; word-break: break-word; }
.bar { position: relative; height: .6rem; background: var(--soft); border: 1px solid var(--border);
       border-radius: 999px; margin: .4rem 0; }
.bar i { position: absolute; inset: 0 auto 0 0; background: var(--accent); border-radius: 999px; }
.bar b { position: absolute; top: -.25rem; bottom: -.25rem; width: 2px; background: var(--error); }
.pager { display: flex; justify-content: space-between; margin-top: 1rem; }
fieldset { border: 1px solid var(--border); border-radius: 8px; margin: 0 0 .8rem; }
fieldset label { margin-right: 1rem; white-space: nowrap; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);
      white-space: nowrap; }
@media (max-width: 640px) { main { padding: 14px; } .hide-small { display: none; } }
"""


def layout(title: str, body: str, *, signed_in: bool = True) -> str:
    nav = (
        '<p class="muted"><a href="/admin/">Liste</a> · '
        '<a href="/admin/sans-reponse">Sans réponse</a> · '
        '<a href="/admin/synthese">Synthèse</a></p>'
        if signed_in
        else ""
    )
    logout = (
        '<form class="inline" method="post" action="/admin/logout">'
        '<button class="link">Se déconnecter</button></form>'
        if signed_in
        else ""
    )
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{escape(title)} — {escape(APP_NAME)}</title><style>{_STYLE}</style></head>"
        f'<body><main><header><h1><a href="/admin/">{escape(title)}</a></h1>{logout}</header>'
        f"{nav}{body}</main></body></html>"
    )


def login_form(error: str | None = None) -> str:
    message = f'<p class="error">{escape(error)}</p>' if error else ""
    return layout(
        "Administration",
        (
            "<p>Relecture du journal des réponses.</p>"
            + message
            + '<form method="post" action="/admin/login">'
            '<label>Mot de passe<br><input type="password" name="password" required '
            'autocomplete="current-password" autofocus></label> '
            "<button>Se connecter</button></form>"
        ),
        signed_in=False,
    )


def _date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m %H:%M")
    except ValueError:
        return iso


def _score(value: float | None) -> str:
    return "–" if value is None else f"{value:.2f}".replace(".", ",")


def _options(choices: dict[str, str], selected: str | None, blank: str) -> str:
    out = [f'<option value="">{escape(blank)}</option>']
    for value, label in choices.items():
        mark = " selected" if value == selected else ""
        out.append(f'<option value="{escape(value)}"{mark}>{escape(label)}</option>')
    return "".join(out)


def _thumb(value: int | None) -> str:
    """👍 or 👎 with its words for screen readers and on hover; empty without a feedback."""
    if value not in FEEDBACK:
        return ""
    words, icon = FEEDBACK[value]
    return (
        f'<span title="{escape(words)}"><span aria-hidden="true">{icon}</span>'
        f'<span class="sr">{escape(words)}</span></span>'
    )


def entries_list(
    rows: list[dict],
    total: int,
    *,
    review: str,
    route: str,
    channel: str,
    text: str,
    page: int,
    feedback: str = "",
    gap: str = "",
    unreviewed_negative: int = 0,
) -> str:
    statuses = {"unreviewed": "Non revues", **{k: LABELS[k] for k in REVIEW_LABELS}}
    shortcut_query = escape(urlencode({"avis": "negatif", "statut": "unreviewed"}))
    shortcut = (
        f'<p><a href="/admin/?{shortcut_query}">Avis négatifs non revus '
        f"({int(unreviewed_negative)})</a> "
        '<span class="muted">: les réponses jugées « Pas utile » par l\'utilisateur, à revoir '
        "en premier.</span></p>"
    )
    filters = (
        '<form class="filters" method="get" action="/admin/">'
        f'<label>Revue<select name="statut">{_options(statuses, review, "Toutes")}</select></label>'
        f'<label>Issue<select name="issue">{_options(ROUTES, route, "Toutes")}</select></label>'
        f'<label>Canal<select name="canal">{_options(CHANNELS, channel, "Tous")}</select></label>'
        f'<label>Avis<select name="avis">{_options(FEEDBACK_CHOICES, feedback, "Tous")}</select>'
        "</label>"
        f'<label>Sans réponse<select name="manque">{_options(GAP_CHOICES, gap, "Indifférent")}'
        "</select></label>"
        f'<label>Recherche<input type="text" name="q" value="{escape(text)}" maxlength="100">'
        "</label><button>Filtrer</button></form>"
    )
    lines = []
    for row in rows:
        question = row["question"]
        shown = question if len(question) <= 120 else question[:117] + "…"
        review_label = LABELS.get(row["review_label"] or "", "–")
        # A refusal already says it went without an answer
        kind = row.get("gap")
        gap_tag = (
            f' <span class="tag">{escape(GAP_KINDS[kind])}</span>'
            if kind in GAP_KINDS and kind != "refus"
            else ""
        )
        lines.append(
            f"<tr><td>{escape(_date(row['created_at']))}</td>"
            f'<td class="hide-small">{escape(CHANNELS.get(row["channel"], row["channel"]))}</td>'
            f'<td><a href="/admin/reponses/{int(row["id"])}">{escape(shown)}</a></td>'
            f'<td><span class="tag">{escape(ROUTES.get(row["route"], row["route"]))}</span>'
            f"{gap_tag}</td>"
            f'<td class="num">{_score(row["top_score"])}</td>'
            f"<td>{_thumb(row.get('feedback'))}</td>"
            f"<td>{escape(review_label)}</td></tr>"
        )
    table = (
        '<table><thead><tr><th>Date (UTC)</th><th class="hide-small">Canal</th><th>Question</th>'
        '<th>Issue</th><th class="num">Score</th><th>Avis</th><th>Revue</th></tr></thead>'
        f"<tbody>{''.join(lines)}</tbody></table>"
        if rows
        else '<p class="muted">Aucune réponse ne correspond.</p>'
    )
    last_page = max(1, -(-total // PAGE_SIZE))
    base = {
        "statut": review,
        "issue": route,
        "canal": channel,
        "avis": feedback,
        "manque": gap,
        "q": text,
    }

    def link(target: int, label: str) -> str:
        query = urlencode({**{k: v for k, v in base.items() if v}, "page": target})
        return f'<a href="/admin/?{escape(query)}">{label}</a>'

    previous = link(page - 1, "← Précédentes") if page > 1 else "<span></span>"
    following = link(page + 1, "Suivantes →") if page < last_page else "<span></span>"
    pager = (
        f'<div class="pager">{previous}'
        f'<span class="muted">{total} réponse(s) · page {page}/{last_page}</span>{following}</div>'
    )
    return layout("Journal des réponses", shortcut + filters + table + pager)


def _sources(sources: list[dict]) -> str:
    if not sources:
        return '<p class="muted">Aucune source.</p>'
    items = []
    for number, src in enumerate(sources, start=1):
        label = str(src.get("title") or src.get("source") or "?")
        if src.get("section") and src["section"] != label:
            label += f" — {src['section']}"
        url = str(src.get("url") or "")
        text = escape(label)
        if url.startswith(("https://", "http://")):
            text = f'<a href="{escape(url)}" rel="noopener noreferrer">{text}</a>'
        items.append(f"<li>[Source {number}] {text} · {_score(src.get('score'))}</li>")
    return f"<ul>{''.join(items)}</ul>"


def _retrieved(hits: list[dict], threshold: float, top_score: float | None) -> str:
    if not hits:
        return '<p class="muted">Aucune recherche (politesse ou erreur).</p>'
    rows = []
    for rank, hit in enumerate(hits, start=1):
        score = hit.get("score")
        above = isinstance(score, int | float) and score >= threshold
        rows.append(
            f'<tr><td>{rank}</td><td class="num">{_score(score)}</td>'
            f"<td>{'≥ seuil' if above else '< seuil'}</td>"
            f"<td>{escape(str(hit.get('source') or ''))}</td>"
            f"<td>{escape(str(hit.get('section') or ''))}</td></tr>"
        )
    best = min(max(top_score or 0.0, 0.0), 1.0) * 100
    mark = min(max(threshold, 0.0), 1.0) * 100
    bar = (
        f'<div class="bar" title="meilleur score / seuil"><i style="width:{best:.0f}%"></i>'
        f'<b style="left:{mark:.0f}%"></b></div>'
        f'<p class="muted">Meilleur score {_score(top_score)} · seuil {_score(threshold)} '
        "(trait rouge)</p>"
    )
    return (
        bar + '<table><thead><tr><th>#</th><th class="num">Score</th><th></th><th>Source</th>'
        f"<th>Section</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _user_feedback(entry: dict) -> str:
    """What the user of the chat thought of the answer (#19); the API has no thumbs."""
    title = "<h2>Avis de l'utilisateur</h2>"
    if entry["channel"] != "chat":
        return (
            title + '<p class="muted">Sans objet : les réponses de l\'API ne reçoivent pas '
            "d'avis.</p>"
        )
    value = entry.get("feedback")
    if value not in FEEDBACK:
        return title + '<p class="muted">Aucun avis.</p>'
    words, icon = FEEDBACK[value]
    when = (
        f"le {escape(_date(entry['feedback_at']))} (UTC)"
        if entry.get("feedback_at")
        else "date inconnue (avis antérieur au 12 octobre 2026)"
    )
    comment = (
        f"<pre>{escape(entry['feedback_comment'])}</pre>"
        if entry.get("feedback_comment")
        else '<p class="muted">Sans commentaire.</p>'
    )
    return (
        f'{title}<p><strong><span aria-hidden="true">{icon}</span> {escape(words)}</strong>'
        f' <span class="muted">· {when}</span></p>{comment}'
    )


def _dl(pairs: list[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in pairs) + "</dl>"


def _move_form(entry_id: int, current: int | None, themes: list[dict], back: int | None) -> str:
    """Move a question to another theme, to a new one, or out of any (#20)."""
    options = "".join(
        f'<option value="{int(t["id"])}"{" selected" if t["id"] == current else ""}>'
        f"{escape(t['name'])}</option>"
        for t in themes
    )
    none = "" if current is not None else " selected"
    back_field = f'<input type="hidden" name="retour" value="{int(back)}">' if back else ""
    return (
        f'<form class="filters" method="post" action="/admin/reponses/{int(entry_id)}/theme">'
        f'<label>Thème<select name="theme"><option value=""{none}>Aucun (à regrouper de '
        f"nouveau)</option>{options}</select></label>"
        f'<label>ou nouveau thème<input type="text" name="nouveau" maxlength="{MAX_NAME}">'
        f"</label>{back_field}<button>Déplacer</button></form>"
    )


def _entry_theme(entry: dict, themes: list[dict], error: str | None) -> str:
    """The theme of a question left without an answer (#20), and the form to move it."""
    problem = f'<p class="error">{escape(error)}</p>' if error else ""
    if not entry.get("gap") and entry.get("gap_theme_id") is None:
        return f"<h2>Thème</h2>{problem}" if problem else ""
    current = entry.get("gap_theme_id")
    named = next((t for t in themes if t["id"] == current), None)
    where = (
        f'<p>Rangée dans le thème <a href="/admin/sans-reponse/{int(named["id"])}">'
        f"{escape(named['name'])}</a>.</p>"
        if named
        else '<p class="muted">Pas encore rangée dans un thème : voir '
        '<a href="/admin/sans-reponse">Sans réponse</a>.</p>'
    )
    return f"<h2>Thème</h2>{problem}{where}{_move_form(int(entry['id']), current, themes, None)}"


def entry_detail(
    entry: dict,
    error: str | None = None,
    themes: list[dict] | None = None,
    theme_error: str | None = None,
) -> str:
    def dash(value: object) -> str:
        return "–" if value in (None, "") else str(value)

    tokens = (
        f"{entry['tokens_in']} → {entry['tokens_out']}" if entry["tokens_in"] is not None else "–"
    )
    # Greetings and errors are no question left without an answer, nor an answered one
    gap = entry.get("gap") or ""
    unanswered = GAP_KINDS.get(gap, "Non" if entry["route"] == "generate" else "–")
    latency = f"{entry['latency_ms']} ms" if entry["latency_ms"] is not None else "–"
    meta = _dl(
        [
            ("Date (UTC)", _date(entry["created_at"])),
            ("Canal", CHANNELS.get(entry["channel"], entry["channel"])),
            ("Issue", ROUTES.get(entry["route"], entry["route"])),
            ("Sans réponse", unanswered),
            ("Modèle réel", dash(entry["llm_model"])),
            ("Alias demandé", dash(entry["llm_alias"])),
            ("Jetons (entrée → sortie)", tokens),
            ("Durée", latency),
            ("Collection", entry["collection"]),
            ("Embedding", entry["embedding_model"]),
            ("Version de l'application", dash(entry["app_version"])),
        ]
    )
    rewritten = (
        f"<h2>Reformulée (relance)</h2><pre>{escape(entry['rewritten'])}</pre>"
        if entry["rewritten"]
        else ""
    )
    failure = (
        f'<h2>Erreur</h2><pre class="error">{escape(entry["error"])}</pre>'
        if entry["error"]
        else ""
    )
    boxes = "".join(
        f'<label><input type="radio" name="label" value="{escape(value)}" required'
        f"{' checked' if entry['review_label'] == value else ''}> {escape(LABELS[value])}</label>"
        for value in REVIEW_LABELS
    )
    problem = f'<p class="error">{escape(error)}</p>' if error else ""
    reviewed = (
        f'<p class="muted">Revue le {escape(_date(entry["reviewed_at"]))}.</p>'
        if entry["reviewed_at"]
        else ""
    )
    promoted = (
        f"<p>Question reprise dans le jeu d'évaluation : <strong>{escape(entry['promoted_as'])}"
        "</strong>.</p>"
        if entry["promoted_as"]
        else ""
    )
    form = (
        f"<h2>Revue</h2>{problem}{reviewed}{promoted}"
        f'<form method="post" action="/admin/reponses/{int(entry["id"])}">'
        f"<fieldset>{boxes}</fieldset>"
        '<label>Note<br><textarea name="note" maxlength="1000">'
        f"{escape(entry['review_note'] or '')}</textarea></label><br>"
        "<button>Enregistrer et passer à la suivante</button> "
        f'<a href="/admin/reponses/{int(entry["id"])}/yaml">Reprendre dans le jeu d\'évaluation</a>'
        "</form>"
    )
    body = (
        '<p><a href="/admin/">← Retour à la liste</a></p>'
        f"<h2>Question</h2><pre>{escape(entry['question'])}</pre>"
        f"{rewritten}"
        f"<h2>Réponse</h2><pre>{escape(entry['answer'] or '(vide)')}</pre>"
        f"{failure}"
        f"{_user_feedback(entry)}"
        f"{_entry_theme(entry, themes or [], theme_error)}"
        f"<h2>Sources citées au modèle</h2>{_sources(entry['sources_list'])}"
        f"<h2>Résultats de la recherche</h2>"
        f"{_retrieved(entry['retrieved_list'], entry['threshold'], entry['top_score'])}"
        f"<h2>Détails</h2>{meta}{form}"
    )
    return layout(f"Réponse n° {int(entry['id'])}", body)


def yaml_page(entry_id: int, question_id: str, excerpt: str, promoted_as: str | None) -> str:
    done = (
        f'<p class="muted">Déjà marquée comme reprise : {escape(promoted_as)}.</p>'
        if promoted_as
        else ""
    )
    return layout(
        f"Extrait pour eval/questions.yaml ({question_id})",
        (
            f'<p><a href="/admin/reponses/{entry_id}">← Retour à la réponse</a></p>'
            "<p>À coller dans <code>eval/questions.yaml</code> via une pull request, après "
            "avoir complété <code>answer_must</code> et relu les sections attendues.</p>"
            f"<pre>{escape(excerpt)}</pre>{done}"
            f'<form method="post" action="/admin/reponses/{entry_id}/promotion">'
            f'<input type="hidden" name="question_id" value="{escape(question_id)}">'
            f"<button>J'ai ajouté cette question ({escape(question_id)})</button></form>"
        ),
    )


def not_found() -> str:
    return layout("Introuvable", '<p>Cette page n\'existe pas. <a href="/admin/">Retour</a></p>')


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f} %" if whole else "–"


def _number(value: float | None, unit: str = "") -> str:
    return "–" if value is None else f"{value:.0f}{unit}"


def _satisfaction(useful: int, votes: int) -> str:
    """The share of "Utile" among the votes, always with the number of votes behind it."""
    if not votes:
        return "—"
    return f"{100 * useful / votes:.0f} % ({votes} vote{'s' if votes > 1 else ''})"


def _feedback_section(feedback: dict) -> str:
    """The thumbs of the chat (#19): per route, in all without the greetings, and against the
    review."""
    title = "<h2>Avis des utilisateurs</h2>"
    routes = feedback["by_route"]
    if not routes:
        return title + '<p class="muted">Aucune réponse du chat sur cette période.</p>'

    def row(name: str, line: dict, strong: bool = False) -> str:
        cells = (
            f'<td class="num">{line["answers"]}</td><td class="num">{line["rated"]}</td>'
            f'<td class="num">{_pct(line["rated"], line["answers"])}</td>'
            f'<td class="num">{line["useful"]}</td><td class="num">{line["not_useful"]}</td>'
            f'<td class="num">{_satisfaction(line["useful"], line["rated"])}</td>'
        )
        label = f"<strong>{escape(name)}</strong>" if strong else escape(name)
        return f"<tr><td>{label}</td>{cells}</tr>"

    lines = [row(name, routes[route]) for route, name in ROUTES.items() if route in routes]
    lines.append(row("Total hors politesse", feedback["total_without_smalltalk"], strong=True))
    per_route = (
        '<p class="muted">Les pouces « Utile / Pas utile » sous les réponses du chat (l\'API '
        "n'en a pas). La satisfaction est la part d'« Utile » parmi les votes ; le total laisse "
        "de côté les réponses de politesse, qui ne disent rien de la qualité.</p>"
        '<table><thead><tr><th>Issue</th><th class="num">Réponses du chat</th>'
        '<th class="num">Avis</th><th class="num">Part notée</th><th class="num">Utile</th>'
        '<th class="num">Pas utile</th><th class="num">Satisfaction</th></tr></thead>'
        f"<tbody>{''.join(lines)}</tbody></table>"
        f"<p>{feedback['comments']} avis avec un commentaire · "
        f'<a href="/admin/?avis=negatif">voir les réponses jugées « Pas utile »</a></p>'
    )

    crosstab = feedback["crosstab"]
    if not crosstab:
        return title + per_route
    labels = [*REVIEW_LABELS, ""]
    cross_rows = "".join(
        f"<tr><td>{escape(FEEDBACK[value][0])}</td>"
        + "".join(f'<td class="num">{crosstab.get((value, label), 0)}</td>' for label in labels)
        + "</tr>"
        for value in (1, 0)
    )
    useful_but_false = crosstab.get((1, "fausse"), 0)
    query = escape(urlencode({"avis": "positif", "statut": "fausse"}))
    alert = (
        f'<p class="error">{useful_but_false} réponse(s) jugée(s) « Utile » par l\'utilisateur '
        f'mais classée(s) fausse(s) à la revue : à regarder en priorité. <a href="/admin/?{query}">'
        "Les voir</a></p>"
        if useful_but_false
        else ""
    )
    cross = (
        "<h2>Avis des utilisateurs et revue</h2>"
        '<p class="muted">Un « Utile » sur une réponse classée fausse est le cas à regarder en '
        "priorité : l'utilisateur a cru une réponse fausse. Un « Pas utile » sur une réponse "
        "bonne signale plutôt une attente que le corpus ne couvre pas.</p>"
        f"{alert}"
        "<table><thead><tr><th>Avis</th>"
        + "".join(f'<th class="num">{escape(LABELS[label])}</th>' for label in REVIEW_LABELS)
        + '<th class="num">Non revues</th></tr></thead>'
        f"<tbody>{cross_rows}</tbody></table>"
    )
    return title + per_route + cross


def _gaps_section(gaps: dict) -> str:
    """The questions left without an answer (#20), per kind, out of the questions that went
    to the search; each kind links to the list of its entries."""
    title = "<h2>Questions sans réponse</h2>"
    questions = gaps["questions"]
    if not questions:
        return title + '<p class="muted">Aucune question sur cette période (hors politesse).</p>'

    def row(label: str, count: int, target: str, strong: bool = False) -> str:
        name = f"<strong>{escape(label)}</strong>" if strong else escape(label)
        query = escape(urlencode({"manque": target}))
        link = f'<a href="/admin/?{query}">voir</a>' if count else ""
        return (
            f'<tr><td>{name}</td><td class="num">{count}</td>'
            f'<td class="num">{_pct(count, questions)}</td><td>{link}</td></tr>'
        )

    kinds = gaps["by_kind"]
    lines = [row(GAP_KINDS[kind], kinds[kind], kind) for kind in WITHOUT_ANSWER]
    lines.append(row(GAP_CHOICES["aucune"], gaps["without_answer"], "aucune", strong=True))
    lines += [row(GAP_KINDS[kind], kinds[kind], kind) for kind in ("incomplete", "pas_utile")]
    return (
        title + f'<p class="muted">Sur les {questions} question(s) de la période qui sont '
        "allées jusqu'à la recherche (politesse et erreurs à part). Refus au seuil, refus du "
        "modèle pour une question hors Ynov et aveux du modèle (« Je ne peux pas répondre… », "
        "« Le contexte ne précise pas… ») n'ont reçu aucune réponse ; les réponses incomplètes "
        "(une partie manque) et celles jugées « Pas utile » par l'utilisateur sont comptées à "
        "part. Les liens mènent à tout le journal, pas seulement à la période.</p>"
        '<table><thead><tr><th>Genre</th><th class="num">Nombre</th>'
        '<th class="num">Part des questions</th><th></th></tr></thead>'
        f"<tbody>{''.join(lines)}</tbody></table>"
        '<p><a href="/admin/sans-reponse">Voir ces questions rangées par thème</a></p>'
    )


def stats_page(data: dict, threshold: float) -> str:
    """The summary: how the answers end, what the users thought of them, how they were
    reviewed, the scores against the threshold, the models that answered, the days and the
    errors."""
    totals = data["totals"]
    total = totals["total"] or 0
    period = data["period"]
    periods = {"7": "7 derniers jours", "30": "30 derniers jours"}
    choose = "".join(
        f'<option value="{value}"{" selected" if value == period else ""}>{label}</option>'
        for value, label in {"": "Tout le journal", **periods}.items()
    )
    head = (
        '<form class="filters" method="get" action="/admin/synthese">'
        f'<label>Période<select name="periode">{choose}</select></label>'
        "<button>Afficher</button></form>"
    )
    if not total:
        return layout("Synthèse", head + '<p class="muted">Aucune réponse sur cette période.</p>')
    reviewed = totals["reviewed"] or 0
    intro = (
        f"<p>{total} réponse(s), du {escape(_date(totals['first']))} au "
        f"{escape(_date(totals['last']))} (UTC) · {reviewed} revue(s) "
        f"({_pct(reviewed, total)}) · {totals['promoted'] or 0} reprise(s) dans le jeu "
        "d'évaluation.</p>"
    )

    labels = list(REVIEW_LABELS)
    route_rows = []
    for route, name in ROUTES.items():
        line = data["by_route"].get(route)
        if line is None:
            continue
        cells = "".join(
            f'<td class="num">{data["crosstab"].get((route, label), 0)}</td>'
            for label in [*labels, ""]
        )
        route_rows.append(
            f"<tr><td>{escape(name)}</td>"
            f'<td class="num">{line["n"]}</td><td class="num">{_pct(line["n"], total)}</td>'
            f'<td class="num">{_score(line["avg_score"])}</td>{cells}</tr>'
        )
    by_route = (
        "<h2>Comment les réponses se terminent</h2>"
        '<table><thead><tr><th>Issue</th><th class="num">Nombre</th><th class="num">Part</th>'
        '<th class="num">Score moyen</th>'
        + "".join(f'<th class="num">{escape(LABELS[label])}</th>' for label in labels)
        + '<th class="num">Non revues</th></tr></thead><tbody>'
        + "".join(route_rows)
        + "</tbody></table>"
    )

    label_rows = "".join(
        f"<tr><td>{escape(LABELS[label])}</td>"
        f'<td class="num">{line["n"]}</td><td class="num">{_score(line["min_score"])}</td>'
        f'<td class="num">{_score(line["avg_score"])}</td>'
        f'<td class="num">{_score(line["max_score"])}</td></tr>'
        for label in labels
        if (line := data["by_label"].get(label))
    )
    by_label = (
        "<h2>Scores de la recherche selon la revue</h2>"
        f'<p class="muted">Seuil actuel : {_score(threshold)}. Une réponse « fausse » ou '
        "« hors sujet » au-dessus du seuil plaide pour le relever ; une « bonne » réponse "
        "juste au-dessus montre la marge qui reste.</p>"
        '<table><thead><tr><th>Revue</th><th class="num">Nombre</th><th class="num">Min</th>'
        '<th class="num">Moyenne</th><th class="num">Max</th></tr></thead>'
        f"<tbody>{label_rows}</tbody></table>"
        if label_rows
        else "<h2>Scores de la recherche selon la revue</h2>"
        '<p class="muted">Aucune réponse revue sur cette période.</p>'
    )

    model_rows = "".join(
        f"<tr><td>{escape(line['model'] or '(inconnu : erreur avant la réponse)')}</td>"
        f'<td class="num">{line["n"]}</td>'
        f'<td class="num">{_number(line["avg_latency"], " ms")}</td>'
        f'<td class="num">{_number(line["avg_in"])} → {_number(line["avg_out"])}</td>'
        f"<td>{escape(_date(line['first']))} → {escape(_date(line['last']))}</td></tr>"
        for line in data["by_model"]
    )
    by_model = (
        "<h2>Modèle qui a répondu</h2>"
        '<p class="muted">Le modèle réel derrière l\'alias : une nouvelle ligne signale un '
        "changement côté Mammouth.</p>"
        '<table><thead><tr><th>Modèle</th><th class="num">Nombre</th>'
        '<th class="num">Durée moyenne</th><th class="num">Jetons moyens (entrée → sortie)</th>'
        f"<th>Vu du … au … (UTC)</th></tr></thead><tbody>{model_rows}</tbody></table>"
        if model_rows
        else ""
    )

    day_rows = "".join(
        f'<tr><td>{escape(line["day"])}</td><td class="num">{line["n"]}</td>'
        f'<td class="num">{line["refused"] or 0}</td>'
        f'<td class="num">{line["errors"] or 0}</td></tr>'
        for line in data["per_day"]
    )
    per_day = (
        "<h2>Par jour</h2>"
        '<table><thead><tr><th>Jour (UTC)</th><th class="num">Réponses</th>'
        '<th class="num">Refus au seuil</th><th class="num">Erreurs</th></tr></thead>'
        f"<tbody>{day_rows}</tbody></table>"
    )

    error_rows = "".join(
        f'<tr><td>{escape(line["cause"])}</td><td class="num">{line["n"]}</td>'
        f"<td>{escape(_date(line['last']))}</td></tr>"
        for line in data["errors"]
    )
    errors = (
        "<h2>Erreurs</h2>"
        '<table><thead><tr><th>Cause</th><th class="num">Nombre</th><th>Dernière (UTC)</th>'
        f"</tr></thead><tbody>{error_rows}</tbody></table>"
        if error_rows
        else ""
    )
    feedback = _feedback_section(data["feedback"])
    gaps = _gaps_section(data["gaps"])
    return layout(
        "Synthèse",
        head + intro + by_route + gaps + feedback + by_label + by_model + per_day + errors,
    )


# --- Questions without an answer, by theme (#20) --------------------------------------------

GROUPING_RESULTS = {
    "busy": "Un regroupement est déjà en cours : réessayez dans une minute.",
    "llm": "Le LLM n'a pas répondu : rien n'a été rangé, réessayez plus tard.",
    "cut": "La réponse du LLM a été coupée, même pour un lot plus petit : rien n'a été rangé.",
    "invalid": "La réponse du LLM n'a pas pu être lue : rien n'a été rangé.",
}
PERIOD_CHOICES = {"": "Tout le journal", "7": "7 derniers jours", "30": "30 derniers jours"}


def grouping_message(result: str, questions: int, new_themes: int) -> tuple[str, bool] | None:
    """The message after a grouping (text, is an error), from the query of the redirect."""
    if result in GROUPING_RESULTS:
        return GROUPING_RESULTS[result], True
    if result != "ok":
        return None
    if not questions:
        return "Aucune question à ranger.", False
    return (
        f"{questions} question(s) rangée(s), dont {new_themes} dans de nouveaux thèmes."
        if new_themes
        else f"{questions} question(s) rangée(s) dans des thèmes existants."
    ), False


def _kinds(by_kind: dict[str, int]) -> str:
    return " · ".join(f"{escape(GAP_KINDS[k])} {n}" for k, n in by_kind.items() if k in GAP_KINDS)


def _cause(cause: str | None) -> str:
    if cause in CAUSES:
        return f'<span class="tag">{escape(CAUSES[cause])}</span>'
    return '<span class="muted">À qualifier</span>'


def themes_page(
    themes: list[dict],
    unthemed_total: int,
    unthemed: list[dict],
    pending: dict[str, int],
    period: str,
    message: tuple[str, bool] | None = None,
) -> str:
    """The themes of the questions left without an answer, the button that groups the new
    ones, and the questions not grouped yet."""
    choose = "".join(
        f'<option value="{value}"{" selected" if value == period else ""}>{label}</option>'
        for value, label in PERIOD_CHOICES.items()
    )
    head = (
        '<form class="filters" method="get" action="/admin/sans-reponse">'
        f'<label>Période<select name="periode">{choose}</select></label>'
        "<button>Afficher</button></form>"
    )
    notice = ""
    if message:
        text, is_error = message
        notice = f'<p class="{"error" if is_error else "muted"}">{escape(text)}</p>'
    waiting = pending["questions"]
    if waiting:
        rest = waiting - pending["next_batch"]
        later = (
            f'<p class="muted">Il en restera {rest} : un appel range au plus {BATCH_SIZE} '
            "questions différentes, relancez ensuite.</p>"
            if rest > 0
            else ""
        )
        grouping = (
            '<form method="post" action="/admin/sans-reponse/regrouper">'
            f"<button>Regrouper {pending['next_batch']} nouvelle(s) question(s) "
            "(1 appel au LLM)</button></form>" + later
        )
    else:
        grouping = '<p class="muted">Toutes les questions sans réponse sont rangées.</p>'
    intro = (
        '<p class="muted">Les questions restées sans réponse (refus, aveux du modèle, réponses '
        "incomplètes, jugées « Pas utile »), rangées par thème par le LLM. Pour chaque thème, "
        "choisissez la cause : un manque de contenu sur le site, une question hors sujet, ou un "
        "défaut de recherche du chatbot (l'information existe mais n'a pas été trouvée). La "
        "période porte sur la date des questions.</p>"
    )
    rows = "".join(
        f'<tr><td><a href="/admin/sans-reponse/{int(t["id"])}">{escape(t["name"])}</a></td>'
        f"<td>{_cause(t['cause'])}</td>"
        f'<td class="num">{t["questions"]}</td><td class="num">{t["conversations"]}</td>'
        f'<td class="hide-small">{_kinds(t["by_kind"])}</td>'
        f"<td>{escape(_date(t['last'] or ''))}</td>"
        f"<td>{escape(t['example'] or '')}</td></tr>"
        for t in themes
    )
    table = (
        "<h2>Thèmes</h2>"
        '<table><thead><tr><th>Thème</th><th>Cause</th><th class="num">Questions</th>'
        '<th class="num">Conversations</th><th class="hide-small">Genres</th>'
        "<th>Dernière (UTC)</th><th>Exemple</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        if rows
        else '<h2>Thèmes</h2><p class="muted">Aucun thème sur cette période.</p>'
    )
    loose = "".join(
        f"<tr><td>{escape(_date(e['created_at']))}</td>"
        f'<td><a href="/admin/reponses/{int(e["id"])}">{escape(e["text"])}</a></td>'
        f"<td>{escape(GAP_KINDS.get(e['kind'] or '', ''))}</td></tr>"
        for e in unthemed
    )
    shown = f" (les {len(unthemed)} plus récentes)" if unthemed_total > len(unthemed) else ""
    not_grouped = (
        f"<h2>Questions non regroupées : {unthemed_total}{shown}</h2>"
        "<table><thead><tr><th>Date (UTC)</th><th>Question</th><th>Genre</th></tr></thead>"
        f"<tbody>{loose}</tbody></table>"
        if unthemed_total
        else ""
    )
    return layout("Questions sans réponse", head + notice + intro + grouping + table + not_grouped)


def _search_now(hits: list[dict], error: str | None, threshold: float) -> str:
    """What the search finds for the example question today (#20), without the LLM."""
    title = "<h2>Ce que la recherche trouve aujourd'hui</h2>"
    explain = (
        '<p class="muted">La question exemple repassée dans la recherche du chatbot, sans le '
        "LLM, sur l'index du moment. La bonne section présente mais sous le seuil ou mal "
        "classée désigne un défaut de recherche ; aucune section qui réponde, un manque de "
        "contenu.</p>"
    )
    if error:
        return title + explain + f'<p class="error">{escape(error)}</p>'
    if not hits:
        return title + explain + '<p class="muted">Aucun résultat.</p>'
    rows = []
    for rank, hit in enumerate(hits, start=1):
        score = hit.get("score")
        above = isinstance(score, int | float) and score >= threshold
        label = str(hit.get("title") or hit.get("source") or "?")
        if hit.get("section") and hit["section"] != label:
            label += f" — {hit['section']}"
        url = str(hit.get("url") or "")
        text = escape(label)
        if url.startswith(("https://", "http://")):
            text = f'<a href="{escape(url)}" rel="noopener noreferrer">{text}</a>'
        rows.append(
            f'<tr><td>{rank}</td><td class="num">{_score(score)}</td>'
            f"<td>{'≥ seuil' if above else '< seuil'}</td><td>{text}</td></tr>"
        )
    return (
        title + explain + '<table><thead><tr><th>#</th><th class="num">Score</th><th></th>'
        f"<th>Section</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
        f'<p class="muted">Seuil actuel : {_score(threshold)}.</p>'
    )


def theme_page(
    theme: dict,
    themes: list[dict],
    hits: list[dict],
    search_error: str | None,
    threshold: float,
    error: str | None = None,
) -> str:
    """A theme: its counts, its cause (with a suggestion), what the search finds today, its
    questions (each can move), and the forms to rename it or merge it into another."""
    theme_id = int(theme["id"])
    problem = f'<p class="error">{escape(error)}</p>' if error else ""
    facts = _dl(
        [
            ("Questions", str(theme["questions"])),
            ("Conversations", str(theme["conversations"])),
            ("Première (UTC)", _date(theme["first"]) if theme["first"] else "–"),
            ("Dernière (UTC)", _date(theme["last"]) if theme["last"] else "–"),
            ("Question exemple", theme["example"] or "–"),
        ]
    )
    kinds = f"<p>{_kinds(theme['by_kind'])}</p>" if theme["by_kind"] else ""
    suggested = theme.get("suggested_cause")
    suggestion = (
        f'<p class="muted">Suggestion : {escape(CAUSES[suggested])} (thème des autres écoles '
        "ou des sujets sans rapport, ou questions surtout refusées comme hors Ynov ou classées "
        "hors sujet à la revue).</p>"
        if suggested in CAUSES and theme["cause"] != suggested
        else ""
    )
    boxes = "".join(
        f'<label><input type="radio" name="cause" value="{escape(value)}"'
        f"{' checked' if theme['cause'] == value else ''}> {escape(label)}</label>"
        for value, label in {**CAUSES, "": "À qualifier"}.items()
    )
    yaml_link = (
        f'<p><a href="/admin/reponses/{int(theme["example_id"])}/yaml">Reprendre la question '
        "exemple dans le jeu d'évaluation</a>, pour mesurer la correction avec eval/.</p>"
        if theme["cause"] == "recherche" and theme.get("example_id")
        else ""
    )
    cause = (
        f"<h2>Cause</h2>{suggestion}"
        f'<form method="post" action="/admin/sans-reponse/{theme_id}/cause">'
        f"<fieldset>{boxes}</fieldset>"
        f'<label>Note<br><textarea name="note" maxlength="{MAX_NOTE}">'
        f"{escape(theme['note'] or '')}</textarea></label><br>"
        "<button>Enregistrer</button></form>" + yaml_link
    )
    question_rows = "".join(
        f"<tr><td>{escape(_date(e['created_at']))}</td>"
        f'<td><a href="/admin/reponses/{int(e["id"])}">{escape(e["text"])}</a></td>'
        f"<td>{escape(GAP_KINDS.get(e['kind'] or '', 'Plus repérée'))}</td>"
        f'<td class="num">{_score(e["top_score"])}</td>'
        f"<td>{escape(LABELS.get(e['review_label'] or '', '–'))}</td>"
        f"<td>{_move_form(int(e['id']), theme_id, themes, theme_id)}</td></tr>"
        for e in theme["entries"]
    )
    questions = (
        f"<h2>Questions ({len(theme['entries'])})</h2>"
        "<table><thead><tr><th>Date (UTC)</th><th>Question</th><th>Genre</th>"
        '<th class="num">Score</th><th>Revue</th><th>Déplacer</th></tr></thead>'
        f"<tbody>{question_rows}</tbody></table>"
        if question_rows
        else '<h2>Questions</h2><p class="muted">Ce thème n\'a plus de question.</p>'
    )
    rename = (
        "<h2>Renommer</h2>"
        f'<form class="filters" method="post" action="/admin/sans-reponse/{theme_id}/nom">'
        f'<label>Nom<input type="text" name="nom" value="{escape(theme["name"])}" '
        f'maxlength="{MAX_NAME}" required></label><button>Renommer</button></form>'
    )
    others = [t for t in themes if t["id"] != theme_id]
    merge = (
        "<h2>Fusionner</h2>"
        '<p class="muted">Toutes les questions de ce thème passent dans le thème choisi, puis '
        "ce thème est supprimé.</p>"
        f'<form class="filters" method="post" action="/admin/sans-reponse/{theme_id}/fusion">'
        '<label>Dans le thème<select name="cible">'
        + "".join(f'<option value="{int(t["id"])}">{escape(t["name"])}</option>' for t in others)
        + "</select></label><button>Fusionner</button></form>"
        if others
        else ""
    )
    body = (
        '<p><a href="/admin/sans-reponse">← Retour aux thèmes</a></p>'
        f"{problem}<h2>En bref</h2>{facts}{kinds}{cause}"
        f"{_search_now(hits, search_error, threshold)}{questions}{rename}{merge}"
    )
    return layout(f"Thème : {theme['name']}", body)
