"""HTML of the admin pages. Server-rendered, no JavaScript (the CSP forbids scripts).

Everything that comes from the journal (a question typed by a stranger, an answer from the
LLM, a URL from the index) goes through `escape`; the answer is shown as preformatted text,
never as Markdown.
"""

from datetime import datetime
from html import escape
from urllib.parse import urlencode

from chat.pages import APP_NAME
from journal.review import PAGE_SIZE, REVIEW_LABELS

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
@media (max-width: 640px) { main { padding: 14px; } .hide-small { display: none; } }
"""


def layout(title: str, body: str, *, signed_in: bool = True) -> str:
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
        f"{body}</main></body></html>"
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


def entries_list(
    rows: list[dict], total: int, *, review: str, route: str, channel: str, text: str, page: int
) -> str:
    statuses = {"unreviewed": "Non revues", **{k: LABELS[k] for k in REVIEW_LABELS}}
    filters = (
        '<form class="filters" method="get" action="/admin/">'
        f'<label>Revue<select name="statut">{_options(statuses, review, "Toutes")}</select></label>'
        f'<label>Issue<select name="issue">{_options(ROUTES, route, "Toutes")}</select></label>'
        f'<label>Canal<select name="canal">{_options(CHANNELS, channel, "Tous")}</select></label>'
        f'<label>Recherche<input type="text" name="q" value="{escape(text)}" maxlength="100">'
        "</label><button>Filtrer</button></form>"
    )
    lines = []
    for row in rows:
        question = row["question"]
        shown = question if len(question) <= 120 else question[:117] + "…"
        review_label = LABELS.get(row["review_label"] or "", "–")
        lines.append(
            f"<tr><td>{escape(_date(row['created_at']))}</td>"
            f'<td class="hide-small">{escape(CHANNELS.get(row["channel"], row["channel"]))}</td>'
            f'<td><a href="/admin/reponses/{int(row["id"])}">{escape(shown)}</a></td>'
            f'<td><span class="tag">{escape(ROUTES.get(row["route"], row["route"]))}</span></td>'
            f'<td class="num">{_score(row["top_score"])}</td>'
            f"<td>{escape(review_label)}</td></tr>"
        )
    table = (
        '<table><thead><tr><th>Date (UTC)</th><th class="hide-small">Canal</th><th>Question</th>'
        '<th>Issue</th><th class="num">Score</th><th>Revue</th></tr></thead>'
        f"<tbody>{''.join(lines)}</tbody></table>"
        if rows
        else '<p class="muted">Aucune réponse ne correspond.</p>'
    )
    last_page = max(1, -(-total // PAGE_SIZE))
    base = {"statut": review, "issue": route, "canal": channel, "q": text}

    def link(target: int, label: str) -> str:
        query = urlencode({**{k: v for k, v in base.items() if v}, "page": target})
        return f'<a href="/admin/?{escape(query)}">{label}</a>'

    previous = link(page - 1, "← Précédentes") if page > 1 else "<span></span>"
    following = link(page + 1, "Suivantes →") if page < last_page else "<span></span>"
    pager = (
        f'<div class="pager">{previous}'
        f'<span class="muted">{total} réponse(s) · page {page}/{last_page}</span>{following}</div>'
    )
    return layout("Journal des réponses", filters + table + pager)


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


def _dl(pairs: list[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in pairs) + "</dl>"


def entry_detail(entry: dict, error: str | None = None) -> str:
    def dash(value: object) -> str:
        return "–" if value in (None, "") else str(value)

    tokens = (
        f"{entry['tokens_in']} → {entry['tokens_out']}" if entry["tokens_in"] is not None else "–"
    )
    latency = f"{entry['latency_ms']} ms" if entry["latency_ms"] is not None else "–"
    meta = _dl(
        [
            ("Date (UTC)", _date(entry["created_at"])),
            ("Canal", CHANNELS.get(entry["channel"], entry["channel"])),
            ("Issue", ROUTES.get(entry["route"], entry["route"])),
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
