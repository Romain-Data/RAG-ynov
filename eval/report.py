"""Generate eval/REPORT.md from eval/results/*.json and eval/edge_cases.yaml.

The report is derived data: never edit it by hand, regenerate it after each run.

Usage:
    uv run python -m eval.report
"""

import yaml

# The figures are shared with the dashboard of /admin: one definition of each
from eval.dashboard import (
    EDGE_CASES,
    STATUS_LABELS,
    VERDICT_ICONS,
    auto_check_agreement,
    collection,
    load_runs,
    mark,
    model,
    score,
    short_id,
)
from eval.results import EVAL_DIR, load_questions

REPORT = EVAL_DIR / "REPORT.md"


def _config_summary(run: dict) -> str:
    c = run.get("config", {})
    if run["kind"] in ("e2e", "conversation"):
        if "chunk_size" in c:
            return f"chunks {c['chunk_size']}, k={c.get('limit', '?')}"
        # A run on a server does not know the chunking: what answered says more
        parts = [f"modèle {model(run) or '?'}"]
        if name := collection(run):
            parts.append(f"collection {name}")
        return ", ".join(parts)
    cap = c.get("max_per_section")
    return (
        f"chunks {c.get('chunk_size')}, k={c.get('limit')}, "
        f"cand={c.get('candidates')}, plafond={cap if cap is not None else '—'}"
    )


def _score(run: dict) -> str:
    s = score(run)
    if run["kind"] == "retrieval":
        refused = s.get("refused_by_threshold")
        in_scope = [r for r in run["results"] if not r.get("out_of_scope")]
        out_scope = [r for r in run["results"] if r.get("out_of_scope")]
        return (
            f"{sum(r['passed'] for r in in_scope)}/{len(in_scope)}"
            + (f" ({refused} ⛔)" if refused else "")
            + (
                f" · hors périmètre {sum(r['passed'] for r in out_scope)}/{len(out_scope)} ⛔"
                if out_scope
                else ""
            )
        )
    if "in_scope_total" in s:
        return (
            f"{s['in_scope_correct']}/{s['in_scope_total']} ✅ · {s['partial']} 🟡 · "
            f"{s['wrong']} ❌ · hors périmètre {s['out_of_scope_correct']}/"
            f"{s['out_of_scope_total']}"
        )
    return f"{s['correct']}/{s['total']} ✅ · {s['partial']} 🟡 · {s['wrong']} ❌"


def build() -> str:
    runs = load_runs().runs
    questions = load_questions()
    cases = yaml.safe_load(EDGE_CASES.read_text(encoding="utf-8"))
    e2e = [r for r in runs if r["kind"] == "e2e"]
    retrieval = [r for r in runs if r["kind"] == "retrieval"]
    conversations = [r for r in runs if r["kind"] == "conversation"]
    out = [
        "# Rapport d'évaluation du RAG",
        "",
        "> Généré par `uv run python -m eval.report` à partir de `eval/results/*.json` et "
        "`eval/edge_cases.yaml` : ne pas modifier à la main.",
        "",
    ]

    out += ["## Synthèse", ""]
    if e2e:
        last = e2e[-1]
        s = score(last)
        out.append(
            f"- **Dernier test de bout en bout** ({last['environment']}, "
            f"`{last['run_id']}`) : {_score(last)} ; {s['refused']} refusée(s), "
            f"{s['no_answer']} sans réponse."
        )
        prod = [r for r in e2e if r["environment"] == "prod"]
        if prod and prod[-1] is not last:
            out.append(f"- **Dernier test en prod** (`{prod[-1]['run_id']}`) : {_score(prod[-1])}.")
    if retrieval:
        last = retrieval[-1]
        out.append(
            f"- **Dernière évaluation de la recherche** (`{last['run_id']}`) : {_score(last)}."
        )
    if conversations:
        last = conversations[-1]
        out.append(f"- **Dernière passe de conversation** (`{last['run_id']}`) : {_score(last)}.")
    open_cases = [c for c in cases if c["status"] in ("open", "mitigated")]
    out.append(
        f"- **Cas limites** : {len(cases)} documentés, dont {len(open_cases)} ouverts "
        f"ou atténués ({', '.join(c['id'] for c in open_cases)})."
    )
    out.append("")

    out += [
        "## Historique des passages",
        "",
        "★ = étape clé, reprise dans la matrice ci-dessous. Recherche : questions dont la "
        "bonne section (ou le fait attendu) est récupérée ; ⛔ = refusée par le seuil. "
        "Bout en bout : réponses jugées correctes.",
        "",
        "| | Passage | Type | Env. | Questions | Configuration | Score |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        out.append(
            f"| {'★' if r.get('milestone') else ''} | `{r['run_id']}` | {r['kind']} | "
            f"{r['environment']} | {r['question_set']} | {_config_summary(r)} | "
            f"{_score(r)} |"
        )
    out.append("")

    # The matrix is per question of questions.yaml: conversation runs have their own table
    milestones = [r for r in runs if r.get("milestone") and r["kind"] != "conversation"]
    out += [
        "## Matrice par question (étapes clés)",
        "",
        "Recherche : ✅ rang de la bonne section · ✅ ctx = fait présent dans le contexte · "
        "❌ absente · (d/m) sections distinctes / requises · ⛔ refusée par le seuil. "
        "Bout en bout : " + " · ".join(f"{i} {v}" for v, i in VERDICT_ICONS.items()) + ".",
        "",
    ]
    header = " | ".join(f"{short_id(r)} {r['kind'][:3]}" for r in milestones)
    out += [f"| Question | {header} |", "|---|" + "---|" * len(milestones)]
    for q in questions:
        cells = []
        for r in milestones:
            res = next((x for x in r["results"] if x["question_id"] == q["id"]), None)
            cells.append(mark(r, res))
        out.append(f"| **{q['id']}** {q['question'][:60]} | {' | '.join(cells)} |")
    out.append("")
    out += ["Colonnes : " + " · ".join(f"`{short_id(r)}` {r['label']}" for r in milestones), ""]

    if conversations:
        last = conversations[-1]
        out += [
            f"## Détail de la dernière passe de conversation (`{last['run_id']}`)",
            "",
            "| Tour | Question | Reformulée | Verdict | Cas limites | Commentaire |",
            "|---|---|---|---|---|---|",
        ]
        for res in last["results"]:
            out.append(
                f"| **{res['question_id']}** | {res['question'][:45]} | "
                f"{(res.get('rewritten') or '—')[:60]} | "
                f"{VERDICT_ICONS.get(res['verdict'], '?')} {res['verdict']} | "
                f"{', '.join(res.get('edge_cases', []))} | "
                f"{res.get('review_note', '').replace('|', '/')} |"
            )
        out.append("")

    if e2e:
        last = e2e[-1]
        out += [
            f"## Détail du dernier test de bout en bout (`{last['run_id']}`)",
            "",
            "| Question | Verdict | Cas limites | Commentaire |",
            "|---|---|---|---|",
        ]
        for res in last["results"]:
            out.append(
                f"| **{res['question_id']}** {res['question'][:55]} | "
                f"{VERDICT_ICONS.get(res['verdict'], '?')} {res['verdict']} | "
                f"{', '.join(res.get('edge_cases', []))} | "
                f"{res.get('review_note', '').replace('|', '/')} |"
            )
        out.append("")

        agreement = auto_check_agreement(e2e)
        out += [
            "### Fiabilité de la vérification automatique",
            "",
            f"Sur les réponses revues à la main, le verdict automatique (`answer_must`) "
            f"concorde dans {agreement.agree}/{agreement.reviewed} cas. Désaccords :",
            "",
        ]
        for run_id, question_id, verdict, automatic in agreement.disagreements:
            out.append(
                f"- `{run_id}` {question_id} : revue **{verdict}**, automatique **{automatic}**"
            )
        out.append("")

    out += [
        "## Cas limites",
        "",
        "| Id | Titre | Statut | Catégorie | Questions | Découvert dans |",
        "|---|---|---|---|---|---|",
    ]
    for c in cases:
        out.append(
            f"| {c['id']} | {c['title']} | {STATUS_LABELS.get(c['status'], c['status'])}"
            f" | {c['category']} | {', '.join(c['questions'])} | "
            f"{'`' + c['discovered_in'] + '`' if c.get('discovered_in') else '—'} |"
        )
    out.append("")
    for c in cases:
        out += [
            f"### {c['id']} — {c['title']}",
            "",
            f"**Statut** : {STATUS_LABELS.get(c['status'], c['status'])} · "
            f"**Catégorie** : {c['category']}"
            + (f" · **Liens** : {', '.join(c['links'])}" if c.get("links") else ""),
            "",
            f"- **Symptôme** : {c['symptom'].strip()}",
            f"- **Preuve** : {c['evidence'].strip()}",
            f"- **Cause** : {c['cause'].strip()}",
            f"- **Correction** : {c['fix'].strip()}",
            "",
        ]

    out += [
        "## Ajouter un passage",
        "",
        "```sh",
        'uv run python -m eval.retrieval --save "libellé"   # recherche, en local',
        'uv run python -m eval.e2e --save "libellé"         # réponses de l\'API (prod)',
        "uv run python -m eval.report                       # régénère ce rapport",
        "```",
        "",
        "Après un test de bout en bout, relire les verdicts automatiques dans le JSON "
        "(`verdict`, `review_note`, `edge_cases`) et passer `milestone` à `true` pour les "
        "étapes à suivre dans la matrice.",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    for name, reason in load_runs().skipped:
        print(f"Passage écarté : {name} ({reason})")
    REPORT.write_text(build(), encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
