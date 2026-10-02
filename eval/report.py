"""Generate eval/REPORT.md from eval/results/*.json and eval/edge_cases.yaml.

The report is derived data: never edit it by hand, regenerate it after each run.

Usage:
    uv run python -m eval.report
"""
import yaml

from eval.results import EVAL_DIR, load_questions, load_runs

REPORT = EVAL_DIR / "REPORT.md"
EDGE_CASES = EVAL_DIR / "edge_cases.yaml"
VERDICT_ICONS = {"correct": "✅", "partial": "🟡", "wrong": "❌", "refused": "⛔",
                 "no_answer": "∅", "error": "⚠️"}
STATUS_LABELS = {"open": "🔴 ouvert", "mitigated": "🟠 atténué", "fixed": "🟢 corrigé",
                 "lesson": "📘 enseignement"}


def _config_summary(run: dict) -> str:
    c = run.get("config", {})
    if run["kind"] == "e2e":
        return f"chunks {c.get('chunk_size', '?')}, k={c.get('limit', '?')}"
    cap = c.get("max_per_section")
    return (f"chunks {c.get('chunk_size')}, k={c.get('limit')}, "
            f"cand={c.get('candidates')}, plafond={cap if cap is not None else '—'}")


def _score(run: dict) -> str:
    s = run["summary"]
    if run["kind"] == "retrieval":
        refused = s.get("refused_by_threshold")
        return f"{s['passed']}/{s['total']}" + (f" ({refused} ⛔)" if refused else "")
    return f"{s['correct']}/{s['total']} ✅ · {s['partial']} 🟡"


def _cell(run: dict, result: dict | None) -> str:
    if result is None:
        return "·"
    if run["kind"] == "e2e":
        return VERDICT_ICONS.get(result["verdict"], "?")
    if result.get("in_context") and not result.get("rank"):
        mark = "✅ ctx"
    elif result["passed"]:
        mark = f"✅ {result['rank']}"
    else:
        mark = "❌" + (f" {result['rank']}" if result.get("rank") else "")
    if result.get("min_distinct", 1) > 1:
        mark += f" ({result['distinct_sections']}/{result['min_distinct']})"
    if result.get("refused_by_threshold"):
        mark += " ⛔"
    return mark


def build() -> str:
    runs = load_runs()
    questions = load_questions()
    cases = yaml.safe_load(EDGE_CASES.read_text(encoding="utf-8"))
    e2e = [r for r in runs if r["kind"] == "e2e"]
    retrieval = [r for r in runs if r["kind"] == "retrieval"]
    out = ["# Rapport d'évaluation du RAG", "",
           "> Généré par `uv run python -m eval.report` à partir de `eval/results/*.json` et "
           "`eval/edge_cases.yaml` : ne pas modifier à la main.", ""]

    out += ["## Synthèse", ""]
    if e2e:
        last = e2e[-1]
        s = last["summary"]
        out.append(f"- **Dernier test de bout en bout** ({last['environment']}, "
                   f"`{last['run_id']}`) : {s['correct']}/{s['total']} correcte(s), "
                   f"{s['partial']} partielle(s), {s['wrong']} fausse(s), "
                   f"{s['refused']} refusée(s), {s['no_answer']} sans réponse.")
    if retrieval:
        last = retrieval[-1]
        out.append(f"- **Dernière évaluation de la recherche** (`{last['run_id']}`) : "
                   f"{_score(last)}.")
    open_cases = [c for c in cases if c["status"] in ("open", "mitigated")]
    out.append(f"- **Cas limites** : {len(cases)} documentés, dont {len(open_cases)} ouverts "
               f"ou atténués ({', '.join(c['id'] for c in open_cases)}).")
    out.append("")

    out += ["## Historique des passages", "",
            "★ = étape clé, reprise dans la matrice ci-dessous. Recherche : questions dont la "
            "bonne section (ou le fait attendu) est récupérée ; ⛔ = refusée par le seuil. "
            "Bout en bout : réponses jugées correctes.", "",
            "| | Passage | Type | Env. | Questions | Configuration | Score |",
            "|---|---|---|---|---|---|---|"]
    for r in runs:
        out.append(f"| {'★' if r.get('milestone') else ''} | `{r['run_id']}` | {r['kind']} | "
                   f"{r['environment']} | {r['question_set']} | {_config_summary(r)} | "
                   f"{_score(r)} |")
    out.append("")

    milestones = [r for r in runs if r.get("milestone")]
    out += ["## Matrice par question (étapes clés)", "",
            "Recherche : ✅ rang de la bonne section · ✅ ctx = fait présent dans le contexte · "
            "❌ absente · (d/m) sections distinctes / requises · ⛔ refusée par le seuil. "
            "Bout en bout : " + " · ".join(f"{i} {v}" for v, i in VERDICT_ICONS.items()) + ".",
            ""]
    header = " | ".join(f"{r['run_id'][11:13]} {r['kind'][:3]}" for r in milestones)
    out += [f"| Question | {header} |", "|---|" + "---|" * len(milestones)]
    for q in questions:
        cells = []
        for r in milestones:
            res = next((x for x in r["results"] if x["question_id"] == q["id"]), None)
            cells.append(_cell(r, res))
        out.append(f"| **{q['id']}** {q['question'][:60]} | {' | '.join(cells)} |")
    out.append("")
    out += ["Colonnes : " + " · ".join(f"`{r['run_id'][11:13]}` {r['label']}"
                                       for r in milestones), ""]

    if e2e:
        last = e2e[-1]
        out += [f"## Détail du dernier test de bout en bout (`{last['run_id']}`)", "",
                "| Question | Verdict | Cas limites | Commentaire |", "|---|---|---|---|"]
        for res in last["results"]:
            out.append(f"| **{res['question_id']}** {res['question'][:55]} | "
                       f"{VERDICT_ICONS.get(res['verdict'], '?')} {res['verdict']} | "
                       f"{', '.join(res.get('edge_cases', []))} | "
                       f"{res.get('review_note', '').replace('|', '/')} |")
        out.append("")

        reviewed = [x for r in e2e for x in r["results"] if "auto_check" in x]
        agree = sum(x["auto_check"]["verdict"] == x["verdict"] for x in reviewed)
        out += ["### Fiabilité de la vérification automatique", "",
                f"Sur les réponses revues à la main, le verdict automatique (`answer_must`) "
                f"concorde dans {agree}/{len(reviewed)} cas. Désaccords :", ""]
        for r in e2e:
            for x in r["results"]:
                if "auto_check" in x and x["auto_check"]["verdict"] != x["verdict"]:
                    out.append(f"- `{r['run_id']}` {x['question_id']} : revue "
                               f"**{x['verdict']}**, automatique **{x['auto_check']['verdict']}**")
        out.append("")

    out += ["## Cas limites", "",
            "| Id | Titre | Statut | Catégorie | Questions | Découvert dans |",
            "|---|---|---|---|---|---|"]
    for c in cases:
        out.append(f"| {c['id']} | {c['title']} | {STATUS_LABELS.get(c['status'], c['status'])}"
                   f" | {c['category']} | {', '.join(c['questions'])} | "
                   f"{'`' + c['discovered_in'] + '`' if c.get('discovered_in') else '—'} |")
    out.append("")
    for c in cases:
        out += [f"### {c['id']} — {c['title']}", "",
                f"**Statut** : {STATUS_LABELS.get(c['status'], c['status'])} · "
                f"**Catégorie** : {c['category']}"
                + (f" · **Liens** : {', '.join(c['links'])}" if c.get("links") else ""), "",
                f"- **Symptôme** : {c['symptom'].strip()}",
                f"- **Preuve** : {c['evidence'].strip()}",
                f"- **Cause** : {c['cause'].strip()}",
                f"- **Correction** : {c['fix'].strip()}", ""]

    out += ["## Ajouter un passage", "",
            "```sh",
            "uv run python -m eval.retrieval --save \"libellé\"   # recherche, en local",
            "uv run python -m eval.e2e --save \"libellé\"         # réponses de l'API (prod)",
            "uv run python -m eval.report                       # régénère ce rapport",
            "```", "",
            "Après un test de bout en bout, relire les verdicts automatiques dans le JSON "
            "(`verdict`, `review_note`, `edge_cases`) et passer `milestone` à `true` pour les "
            "étapes à suivre dans la matrice.", ""]
    return "\n".join(out)


def main() -> None:
    REPORT.write_text(build(), encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
