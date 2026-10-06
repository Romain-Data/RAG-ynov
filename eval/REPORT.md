# Rapport d'évaluation du RAG

> Généré par `uv run python -m eval.report` à partir de `eval/results/*.json` et `eval/edge_cases.yaml` : ne pas modifier à la main.

## Synthèse

- **Dernier test de bout en bout** (local, `2026-10-06_02_hybride-bm25`) : 20/22 ✅ · 1 🟡 · 1 ❌ · hors périmètre 10/10 ; 0 refusée(s), 0 sans réponse.
- **Dernier test en prod** (`2026-10-02_35_prod-apres-ec14-ec15`) : 12/16 ✅ · 3 🟡 · 0 ❌ · hors périmètre 10/10.
- **Dernière évaluation de la recherche** (`2026-10-06_01_hybride-bm25`) : 22/22 · hors périmètre 8/8 ⛔.
- **Dernière passe de conversation** (`2026-10-06_03_hybride-bm25-c02`) : 3/3 ✅ · 0 🟡 · 0 ❌.
- **Cas limites** : 18 documentés, dont 5 ouverts ou atténués (EC-06, EC-07, EC-11, EC-16, EC-17).

## Historique des passages

★ = étape clé, reprise dans la matrice ci-dessous. Recherche : questions dont la bonne section (ou le fait attendu) est récupérée ; ⛔ = refusée par le seuil. Bout en bout : réponses jugées correctes.

| | Passage | Type | Env. | Questions | Configuration | Score |
|---|---|---|---|---|---|---|
| ★ | `2026-10-02_01_e2e-prod-premier-test` | e2e | prod | v4 | chunks 500, k=5 | 2/6 ✅ · 2 🟡 · 1 ❌ |
| ★ | `2026-10-02_02_retrieval-baseline-500-k5` | retrieval | local | v1 | chunks 500, k=5, cand=5, plafond=— | 9/16 |
|  | `2026-10-02_03_retrieval-500-k10` | retrieval | local | v1 | chunks 500, k=10, cand=10, plafond=— | 10/16 |
| ★ | `2026-10-02_04_retrieval-500-k10-cap2` | retrieval | local | v1 | chunks 500, k=10, cand=40, plafond=2 | 10/16 |
|  | `2026-10-02_05_retrieval-500-k10-cap1` | retrieval | local | v1 | chunks 500, k=10, cand=60, plafond=1 | 11/16 |
| ★ | `2026-10-02_06_retrieval-prefixe-long-k5` | retrieval | local | v1 | chunks 500, k=5, cand=5, plafond=— | 7/16 |
|  | `2026-10-02_07_retrieval-prefixe-long-k10` | retrieval | local | v1 | chunks 500, k=10, cand=10, plafond=— | 9/16 |
|  | `2026-10-02_08_retrieval-prefixe-long-k10-cap2` | retrieval | local | v1 | chunks 500, k=10, cand=40, plafond=2 | 9/16 |
|  | `2026-10-02_09_retrieval-prefixe-long-k10-cap1` | retrieval | local | v1 | chunks 500, k=10, cand=60, plafond=1 | 10/16 |
| ★ | `2026-10-02_10_retrieval-300-prefixe-court-k5` | retrieval | local | v1 | chunks 300, k=5, cand=5, plafond=— | 8/16 |
|  | `2026-10-02_11_retrieval-300-prefixe-court-k10` | retrieval | local | v1 | chunks 300, k=10, cand=10, plafond=— | 9/16 |
|  | `2026-10-02_12_retrieval-300-prefixe-court-k10-cap2` | retrieval | local | v1 | chunks 300, k=10, cand=40, plafond=2 | 9/16 |
|  | `2026-10-02_13_retrieval-300-prefixe-court-k10-cap1` | retrieval | local | v1 | chunks 300, k=10, cand=60, plafond=1 | 11/16 |
|  | `2026-10-02_14_retrieval-lieux-qr-k5` | retrieval | local | v1 | chunks 300, k=5, cand=5, plafond=— | 9/16 |
|  | `2026-10-02_15_retrieval-lieux-qr-k10` | retrieval | local | v1 | chunks 300, k=10, cand=10, plafond=— | 11/16 |
|  | `2026-10-02_16_retrieval-lieux-qr-k10-cap2` | retrieval | local | v1 | chunks 300, k=10, cand=40, plafond=2 | 11/16 |
|  | `2026-10-02_17_retrieval-lieux-qr-k10-cap1` | retrieval | local | v1 | chunks 300, k=10, cand=60, plafond=1 | 11/16 |
|  | `2026-10-02_18_retrieval-lieux-qr-k5-qs-v2` | retrieval | local | v2 | chunks 300, k=5, cand=5, plafond=— | 10/16 |
|  | `2026-10-02_19_retrieval-lieux-qr-k10-qs-v2` | retrieval | local | v2 | chunks 300, k=10, cand=10, plafond=— | 12/16 |
|  | `2026-10-02_20_retrieval-lieux-qr-k10-cap2-qs-v2` | retrieval | local | v2 | chunks 300, k=10, cand=40, plafond=2 | 12/16 |
|  | `2026-10-02_21_retrieval-lieux-qr-k10-cap1-qs-v2` | retrieval | local | v2 | chunks 300, k=10, cand=60, plafond=1 | 12/16 |
| ★ | `2026-10-02_22_retrieval-final-pr5` | retrieval | local | v3 | chunks 300, k=10, cand=40, plafond=2 | 14/16 (1 ⛔) |
| ★ | `2026-10-02_23_e2e-prod-apres-pr5-pr6` | e2e | prod | v4 | chunks 300, k=10 | 10/16 ✅ · 3 🟡 · 1 ❌ |
|  | `2026-10-02_24_verification-outil-reporting` | retrieval | local | v4 | chunks 300, k=10, cand=40, plafond=2 | 14/16 (1 ⛔) |
| ★ | `2026-10-02_25_local-avant-prompt-seuil` | e2e | local | v5 | chunks 300, k=10 | 10/16 ✅ · 3 🟡 · 1 ❌ · hors périmètre 10/10 |
|  | `2026-10-02_26_local-apres-prompt-seuil` | e2e | local | v5 | chunks 300, k=10 | 12/16 ✅ · 3 🟡 · 1 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-02_27_local-apres-prompt-v2` | e2e | local | v5 | chunks 300, k=10 | 12/16 ✅ · 3 🟡 · 0 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-02_28_calibration-seuil-0-45` | retrieval | local | v5 | chunks 300, k=10, cand=40, plafond=2 | 14/16 · hors périmètre 8/8 ⛔ |
| ★ | `2026-10-02_29_prod-apres-prompt-seuil` | e2e | prod | v6 | chunks ?, k=? | 12/16 ✅ · 3 🟡 · 0 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-02_30_modele-minilm-300` | retrieval | local | v6 | chunks 300, k=10, cand=40, plafond=2 | 14/16 · hors périmètre 8/8 ⛔ |
| ★ | `2026-10-02_31_modele-mpnet-300` | retrieval | local | v6 | chunks 300, k=10, cand=40, plafond=2 | 12/16 · hors périmètre 7/8 ⛔ |
| ★ | `2026-10-02_32_modele-e5-large-300` | retrieval | local | v6 | chunks 300, k=10, cand=40, plafond=2 | 15/16 · hors périmètre 0/8 ⛔ |
| ★ | `2026-10-02_33_modele-e5-large-500` | retrieval | local | v6 | chunks 500, k=10, cand=40, plafond=2 | 15/16 · hors périmètre 0/8 ⛔ |
| ★ | `2026-10-02_34_local-e5-large-300` | e2e | local | v7 | chunks 300, k=10 | 12/16 ✅ · 3 🟡 · 1 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-02_35_prod-apres-ec14-ec15` | e2e | prod | v7 | chunks ?, k=? | 12/16 ✅ · 3 🟡 · 0 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-02_36_modele-e5-large-300-corpus-corrige` | retrieval | local | v7 | chunks 300, k=10, cand=40, plafond=2 | 15/16 · hors périmètre 0/8 ⛔ |
| ★ | `2026-10-02_37_modele-minilm-300-corpus-corrige` | retrieval | local | v7 | chunks 300, k=10, cand=40, plafond=2 | 14/16 · hors périmètre 8/8 ⛔ |
| ★ | `2026-10-02_38_local-e5-large-300-corpus-corrige` | e2e | local | v7 | chunks 300, k=10 | 13/16 ✅ · 3 🟡 · 0 ❌ · hors périmètre 10/10 |
|  | `2026-10-03_01_local-avant-graphe-conversation` | e2e | local | v7 | chunks 300, k=10 | 11/16 ✅ · 4 🟡 · 0 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-03_02_local-apres-graphe-conversation` | e2e | local | v7 | chunks 300, k=10 | 11/16 ✅ · 4 🟡 · 0 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-03_04_local-conversations-jeu-c2` | conversation | local | c2 | chunks 300, k=10 | 14/17 ✅ · 0 🟡 · 0 ❌ · hors périmètre 1/1 |
|  | `2026-10-04_02_preprod-mistral-small-2603` | e2e | preprod | v7 | chunks ?, k=? | 11/16 ✅ · 2 🟡 · 1 ❌ · hors périmètre 10/10 |
|  | `2026-10-04_03_preprod-mistral-medium-3-1` | e2e | preprod | v7 | chunks ?, k=? | 11/16 ✅ · 2 🟡 · 2 ❌ · hors périmètre 10/10 |
|  | `2026-10-04_04_preprod-gpt-4-1-mini` | e2e | preprod | v7 | chunks ?, k=? | 11/16 ✅ · 3 🟡 · 1 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-04_05_preprod-mammouth-recommended` | e2e | preprod | v7 | chunks ?, k=? | 11/16 ✅ · 3 🟡 · 0 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-05_01_contexte-reference` | retrieval | local | v8 | chunks 300, k=10, cand=40, plafond=2 | 18/22 · hors périmètre 8/8 ⛔ |
| ★ | `2026-10-05_02_section-entiere` | retrieval | local | v8 | chunks 300, k=10, cand=40, plafond=2 | 18/22 · hors périmètre 8/8 ⛔ |
| ★ | `2026-10-05_03_section-entiere` | e2e | local | v8 | chunks 300, k=10 | 15/22 ✅ · 4 🟡 · 1 ❌ · hors périmètre 10/10 |
|  | `2026-10-05_04_programme-et-blocs` | retrieval | local | v8 | chunks 300, k=10, cand=40, plafond=2 | 18/22 · hors périmètre 7/8 ⛔ |
| ★ | `2026-10-05_05_programme-et-blocs-seuil-0-47` | retrieval | local | v8 | chunks 300, k=10, cand=40, plafond=2 | 18/22 · hors périmètre 8/8 ⛔ |
| ★ | `2026-10-05_06_programme-et-blocs` | e2e | local | v9 | chunks 300, k=10 | 18/22 ✅ · 2 🟡 · 0 ❌ · hors périmètre 10/10 |
| ★ | `2026-10-06_01_hybride-bm25` | retrieval | local | v9 | chunks 300, k=10, cand=40, plafond=2 | 22/22 · hors périmètre 8/8 ⛔ |
| ★ | `2026-10-06_02_hybride-bm25` | e2e | local | v9 | chunks 300, k=10 | 20/22 ✅ · 1 🟡 · 1 ❌ · hors périmètre 10/10 |
|  | `2026-10-06_03_hybride-bm25-c02` | conversation | local | c2 | chunks 300, k=10 | 3/3 ✅ · 0 🟡 · 0 ❌ |

## Matrice par question (étapes clés)

Recherche : ✅ rang de la bonne section · ✅ ctx = fait présent dans le contexte · ❌ absente · (d/m) sections distinctes / requises · ⛔ refusée par le seuil. Bout en bout : ✅ correct · 🟡 partial · ❌ wrong · ⛔ refused · ∅ no_answer · ⚠️ error.

| Question | 10-02_01 e2e | 10-02_02 ret | 10-02_04 ret | 10-02_06 ret | 10-02_10 ret | 10-02_22 ret | 10-02_23 e2e | 10-02_25 e2e | 10-02_27 e2e | 10-02_28 ret | 10-02_29 e2e | 10-02_30 ret | 10-02_31 ret | 10-02_32 ret | 10-02_33 ret | 10-02_34 e2e | 10-02_35 e2e | 10-02_36 ret | 10-02_37 ret | 10-02_38 e2e | 10-03_02 e2e | 10-04_05 e2e | 10-05_01 ret | 10-05_02 ret | 10-05_03 e2e | 10-05_05 ret | 10-05_06 e2e | 10-06_01 ret | 10-06_02 e2e |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **q01** Combien coûte le Mastère Expert en intelligence artificielle | ✅ | ✅ 2 | ✅ 2 | ✅ 2 | ✅ 2 | ✅ 2 | ✅ | ✅ | ✅ | ✅ 2 | ✅ | ✅ 2 | ✅ 2 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ 1 | ✅ 2 | ✅ | ✅ | ✅ | ✅ 2 | ✅ 2 | ✅ | ✅ 2 | ✅ | ✅ 2 | ✅ |
| **q02** Dans quelles villes est proposé le Mastère Expert en intelli | ∅ | ❌ | ❌ | ❌ | ❌ | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q03** Le Mastère Game Programmer est-il proposé à Lyon ? | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ ctx | ❌ | ❌ | ✅ | ✅ ctx | ✅ | ✅ ctx | ✅ 2 | ✅ 2 | ✅ 2 | ✅ | ✅ | ✅ 2 | ✅ ctx | ✅ | ✅ | ✅ | ✅ ctx | ✅ ctx | ✅ | ✅ ctx | ✅ | ✅ 9 | ✅ |
| **q04** Le Mastère Expert en cybersécurité - Pentester se fait-il en | · | ❌ | ❌ | ❌ | ❌ | ✅ ctx | ✅ | ✅ | ✅ | ✅ ctx | ✅ | ✅ ctx | ✅ ctx | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ 1 | ✅ ctx | ✅ | ✅ | ✅ | ✅ ctx | ✅ ctx | ✅ | ✅ ctx | ✅ | ✅ ctx | ✅ |
| **q05** Où peut-on suivre le BTS ERA ? | · | ❌ | ✅ 7 | ❌ | ❌ | ✅ 6 | ✅ | ✅ | ✅ | ✅ 6 | ✅ | ✅ 6 | ✅ 8 | ✅ 4 | ✅ 2 | ✅ | ✅ | ✅ 4 | ✅ 6 | ✅ | ✅ | ✅ | ✅ 6 | ✅ 6 | ✅ | ✅ 6 | ✅ | ✅ 6 | ✅ |
| **q06** Combien de temps dure le Bachelor Informatique ? | · | ❌ | ❌ | ❌ | ❌ | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ 5 | ✅ 3 | ✅ 1 | ✅ | ✅ | ✅ 3 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q07** Peut-on payer les frais de scolarité en plusieurs fois ? | 🟡 | ✅ 3 | ✅ 3 | ✅ 3 | ✅ 4 | ✅ 4 | 🟡 | 🟡 | 🟡 | ✅ 4 | 🟡 | ✅ 4 | ❌ | ✅ 6 | ✅ 2 | 🟡 | 🟡 | ✅ 4 | ✅ 4 | 🟡 | 🟡 | ∅ | ✅ 4 | ✅ 4 | 🟡 | ✅ 4 | 🟡 | ✅ 4 | 🟡 |
| **q08** Quels sont les blocs de compétences du titre RNCP Expert en  | 🟡 | ❌ (0/3) | ❌ 8 (1/3) | ❌ 3 (1/3) | ❌ (0/3) | ❌ 8 (1/3) | 🟡 | 🟡 | 🟡 | ❌ 8 (1/3) | 🟡 | ❌ 8 (1/3) | ❌ 8 (2/3) | ❌ 3 (1/3) | ❌ 1 (2/3) | 🟡 | 🟡 | ❌ 3 (1/3) | ❌ 8 (1/3) | 🟡 | 🟡 | 🟡 | ❌ 8 (1/3) | ❌ 8 (1/3) | 🟡 | ❌ 9 (1/3) | ✅ | ✅ 1 | ✅ |
| **q09** Quel est le numéro de téléphone du campus de Bordeaux ? | ✅ | ✅ 1 | ✅ 1 | ✅ 4 | ✅ 5 | ✅ 5 | ✅ | ✅ | ✅ | ✅ 5 | ✅ | ✅ 5 | ✅ 6 | ✅ 1 | ✅ 2 | ✅ | ✅ | ✅ 1 | ✅ 2 | ✅ | ✅ | ✅ | ✅ 2 | ✅ 2 | ✅ | ✅ 2 | ✅ | ✅ 2 | ✅ |
| **q10** Quels modules sont enseignés en Mastère 2 du Mastère Expert  | · | ✅ 1 | ✅ 1 | ❌ | ✅ 1 | ✅ 1 | 🟡 | 🟡 | 🟡 | ✅ 1 | 🟡 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | 🟡 | 🟡 | ✅ 1 | ✅ 1 | 🟡 | 🟡 | 🟡 | ✅ 1 | ✅ 1 | 🟡 | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q11** Comment se passe l'entretien d'admission chez Ynov ? | · | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | 🟡 | 🟡 | ✅ 1 | ✅ 1 | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q12** Combien coûte une VAE chez Ynov ? | · | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q13** Quelle est l'adresse e-mail du référent handicap de Lyon ? | · | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 2 | ✅ 2 ⛔ | ⛔ | ⛔ | ✅ | ✅ 2 | ✅ | ✅ 2 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ 1 | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q14** Quels métiers peut-on exercer après le Mastère Data engineer | · | ✅ 1 | ✅ 1 | ❌ | ✅ 2 | ✅ 2 | ✅ | ✅ | ✅ | ✅ 2 | ✅ | ✅ 2 | ✅ 3 | ✅ 1 | ✅ 2 | ✅ | ✅ | ✅ 1 | ✅ 2 | ✅ | ✅ | ✅ | ✅ 2 | ✅ 2 | ✅ | ✅ 2 | ✅ | ✅ 2 | ✅ |
| **q15** Quel est le taux de réussite du titre Expert en développemen | · | ✅ 1 | ✅ 1 | ✅ 3 | ❌ | ✅ 6 | ✅ | ✅ | ✅ | ✅ 6 | ✅ | ✅ 6 | ❌ | ✅ 2 | ✅ 1 | ❌ | ✅ | ✅ 1 | ✅ 6 | ✅ | ✅ | ✅ | ✅ 6 | ✅ 6 | ✅ | ✅ 6 | ✅ | ✅ 6 | ✅ |
| **q16** Quels BTS sont accessibles via Parcoursup ? | · | ❌ | ❌ | ❌ | ❌ | ❌ | ∅ | ∅ | ∅ | ❌ | ∅ | ❌ | ❌ | ✅ 1 | ✅ 1 | ✅ | ∅ | ✅ 1 | ❌ | ✅ | ∅ | ∅ | ❌ | ❌ | ∅ | ❌ | ∅ | ✅ 9 | ✅ |
| **q17** Quelle est la capitale de l'Australie ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q18** Donne-moi une recette de pâte à crêpes. | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q19** Quels sont les frais de scolarité de HEC Paris ? | · | · | · | · | · | · | · | ✅ | ✅ | · | ✅ | · | · | · | · | ✅ | ✅ | · | · | ✅ | ✅ | ✅ | · | · | ✅ | · | ✅ | · | ✅ |
| **q20** Quel temps fera-t-il demain à Lyon ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q21** Comment réparer une fuite d'eau sous un évier ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q22** Qui a gagné la Coupe du monde de football 2018 ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q23** Quel est le meilleur langage de programmation pour débuter ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q24** Peux-tu m'écrire un poème sur l'automne ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q25** Combien coûte un abonnement Netflix ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ None ⛔ | ✅ | ✅ | ✅ | ✅ None ⛔ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ | ✅ None ⛔ | ✅ |
| **q26** Quelles sont les conditions d'admission à Polytechnique ? | · | · | · | · | · | · | · | ✅ | ✅ | · | ✅ | · | · | · | · | ✅ | ✅ | · | · | ✅ | ✅ | ✅ | · | · | ✅ | · | ✅ | · | ✅ |
| **q27** Quels sont les blocs de compétences du titre RNCP Expert en  | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ❌ 3 (2/4) | ❌ 3 (2/4) | 🟡 | ❌ 4 (2/4) | ✅ | ✅ 1 | ✅ |
| **q28** Quels modules sont enseignés en Bachelor 1 Cybersécurité ? | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ✅ 1 | ✅ 1 | 🟡 | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q29** Combien de temps a-t-on pour valider son inscription après l | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ✅ 6 | ✅ 6 | ✅ | ✅ 6 | ✅ | ✅ 6 | ✅ |
| **q30** Quelle remise obtient-on en payant les frais de scolarité co | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ✅ 2 | ✅ 2 | ✅ | ✅ 2 | ✅ | ✅ 2 | ✅ |
| **q31** Les Bachelors Ynov passent-ils par Parcoursup ? | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ✅ 1 | ✅ 1 | ✅ | ✅ 1 | ✅ | ✅ 1 | ✅ |
| **q32** Quel niveau faut-il pour entrer en BTS ERA ? | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ❌ | ❌ | ∅ | ❌ | ∅ | ✅ 9 | ✅ |

Colonnes : `10-02_01` e2e-prod-premier-test · `10-02_02` retrieval-baseline-500-k5 · `10-02_04` retrieval-500-k10-cap2 · `10-02_06` retrieval-prefixe-long-k5 · `10-02_10` retrieval-300-prefixe-court-k5 · `10-02_22` retrieval-final-pr5 · `10-02_23` e2e-prod-apres-pr5-pr6 · `10-02_25` local-avant-prompt-seuil · `10-02_27` local-apres-prompt-v2 · `10-02_28` calibration-seuil-0-45 · `10-02_29` prod-apres-prompt-seuil · `10-02_30` modele-minilm-300 · `10-02_31` modele-mpnet-300 · `10-02_32` modele-e5-large-300 · `10-02_33` modele-e5-large-500 · `10-02_34` local-e5-large-300 · `10-02_35` prod-apres-ec14-ec15 · `10-02_36` modele-e5-large-300-corpus-corrige · `10-02_37` modele-minilm-300-corpus-corrige · `10-02_38` local-e5-large-300-corpus-corrige · `10-03_02` local-apres-graphe-conversation · `10-04_05` preprod-mammouth-recommended · `10-05_01` contexte-reference · `10-05_02` section-entiere · `10-05_03` section-entiere · `10-05_05` programme-et-blocs-seuil-0-47 · `10-05_06` programme-et-blocs · `10-06_01` hybride-bm25 · `10-06_02` hybride-bm25

## Détail de la dernière passe de conversation (`2026-10-06_03_hybride-bm25-c02`)

| Tour | Question | Reformulée | Verdict | Cas limites | Commentaire |
|---|---|---|---|---|---|
| **c02.1** | Où peut-on suivre le BTS ERA ? | — | ✅ correct |  |  |
| **c02.2** | Et combien de temps dure-t-il ? | Combien de temps dure le BTS ERA ? | ✅ correct |  |  |
| **c02.3** | Quel niveau faut-il pour y entrer ? | Quel niveau faut-il pour entrer en BTS ERA (Étude et Réalisa | ✅ correct |  |  |

## Détail du dernier test de bout en bout (`2026-10-06_02_hybride-bm25`)

| Question | Verdict | Cas limites | Commentaire |
|---|---|---|---|
| **q01** Combien coûte le Mastère Expert en intelligence artific | ✅ correct |  |  |
| **q02** Dans quelles villes est proposé le Mastère Expert en in | ✅ correct |  |  |
| **q03** Le Mastère Game Programmer est-il proposé à Lyon ? | ✅ correct |  |  |
| **q04** Le Mastère Expert en cybersécurité - Pentester se fait- | ✅ correct |  |  |
| **q05** Où peut-on suivre le BTS ERA ? | ✅ correct |  |  |
| **q06** Combien de temps dure le Bachelor Informatique ? | ✅ correct |  |  |
| **q07** Peut-on payer les frais de scolarité en plusieurs fois  | 🟡 partial | EC-06 | Même omission qu'aux passages 03 et 06 : la remise de 500 € est dans le contexte, pas dans la réponse. |
| **q08** Quels sont les blocs de compétences du titre RNCP Exper | ✅ correct |  |  |
| **q09** Quel est le numéro de téléphone du campus de Bordeaux ? | ✅ correct |  |  |
| **q10** Quels modules sont enseignés en Mastère 2 du Mastère Ex | ✅ correct |  |  |
| **q11** Comment se passe l'entretien d'admission chez Ynov ? | ✅ correct |  |  |
| **q12** Combien coûte une VAE chez Ynov ? | ✅ correct |  |  |
| **q13** Quelle est l'adresse e-mail du référent handicap de Lyo | ✅ correct |  |  |
| **q14** Quels métiers peut-on exercer après le Mastère Data eng | ✅ correct |  |  |
| **q15** Quel est le taux de réussite du titre Expert en dévelop | ✅ correct |  |  |
| **q16** Quels BTS sont accessibles via Parcoursup ? | ✅ correct | EC-07 | Les trois BTS (CIEL, SIO SLAM, SIO SISR), sans en nommer d'autre : la section Parcoursup est récupérée par le BM25. |
| **q17** Quelle est la capitale de l'Australie ? | ✅ correct |  |  |
| **q18** Donne-moi une recette de pâte à crêpes. | ✅ correct |  |  |
| **q19** Quels sont les frais de scolarité de HEC Paris ? | ✅ correct |  |  |
| **q20** Quel temps fera-t-il demain à Lyon ? | ✅ correct |  |  |
| **q21** Comment réparer une fuite d'eau sous un évier ? | ✅ correct |  |  |
| **q22** Qui a gagné la Coupe du monde de football 2018 ? | ✅ correct |  |  |
| **q23** Quel est le meilleur langage de programmation pour débu | ✅ correct |  |  |
| **q24** Peux-tu m'écrire un poème sur l'automne ? | ✅ correct |  |  |
| **q25** Combien coûte un abonnement Netflix ? | ✅ correct |  |  |
| **q26** Quelles sont les conditions d'admission à Polytechnique | ✅ correct |  |  |
| **q27** Quels sont les blocs de compétences du titre RNCP Exper | ✅ correct |  |  |
| **q28** Quels modules sont enseignés en Bachelor 1 Cybersécurit | ✅ correct |  |  |
| **q29** Combien de temps a-t-on pour valider son inscription ap | ✅ correct |  |  |
| **q30** Quelle remise obtient-on en payant les frais de scolari | ✅ correct |  |  |
| **q31** Les Bachelors Ynov passent-ils par Parcoursup ? | ✅ correct |  |  |
| **q32** Quel niveau faut-il pour entrer en BTS ERA ? | ✅ correct | EC-07 | « BAC ou BAC+2 » : fidèle à la fiche (section Infos clés, trouvée grâce au BM25). La regex exigeait « BAC et BAC+2 » (corrigée en v10). |

### Fiabilité de la vérification automatique

Sur les réponses revues à la main, le verdict automatique (`answer_must`) concorde dans 435/456 cas. Désaccords :

- `2026-10-02_01_e2e-prod-premier-test` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_23_e2e-prod-apres-pr5-pr6` q11 : revue **correct**, automatique **wrong**
- `2026-10-02_25_local-avant-prompt-seuil` q11 : revue **correct**, automatique **wrong**
- `2026-10-02_26_local-apres-prompt-seuil` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_26_local-apres-prompt-seuil` q11 : revue **correct**, automatique **wrong**
- `2026-10-02_27_local-apres-prompt-v2` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_27_local-apres-prompt-v2` q11 : revue **correct**, automatique **partial**
- `2026-10-02_29_prod-apres-prompt-seuil` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_29_prod-apres-prompt-seuil` q11 : revue **correct**, automatique **partial**
- `2026-10-02_34_local-e5-large-300` q07 : revue **partial**, automatique **correct**
- `2026-10-02_34_local-e5-large-300` q11 : revue **correct**, automatique **partial**
- `2026-10-02_35_prod-apres-ec14-ec15` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_35_prod-apres-ec14-ec15` q11 : revue **correct**, automatique **partial**
- `2026-10-02_38_local-e5-large-300-corpus-corrige` q11 : revue **correct**, automatique **partial**
- `2026-10-03_01_local-avant-graphe-conversation` q07 : revue **partial**, automatique **wrong**
- `2026-10-03_01_local-avant-graphe-conversation` q11 : revue **partial**, automatique **wrong**
- `2026-10-03_02_local-apres-graphe-conversation` q07 : revue **partial**, automatique **wrong**
- `2026-10-03_02_local-apres-graphe-conversation` q11 : revue **partial**, automatique **wrong**
- `2026-10-05_03_section-entiere` q28 : revue **partial**, automatique **wrong**
- `2026-10-05_06_programme-et-blocs` q11 : revue **correct**, automatique **partial**
- `2026-10-06_02_hybride-bm25` q32 : revue **correct**, automatique **wrong**

## Cas limites

| Id | Titre | Statut | Catégorie | Questions | Découvert dans |
|---|---|---|---|---|---|
| EC-01 | Les embeddings ne lisent que 128 tokens | 🟢 corrigé | chunking | q02, q05, q06 | `2026-10-02_09_retrieval-prefixe-long-k10-cap1` |
| EC-02 | Question refusée à 0,003 du seuil de pertinence | 🟢 corrigé | grading | q13 | `2026-10-02_23_e2e-prod-apres-pr5-pr6` |
| EC-03 | Le LLM préfère une note de bas de page à l'information de lieu | 🟢 corrigé | generation | q03 | `2026-10-02_01_e2e-prod-premier-test` |
| EC-04 | Les tableaux d'équivalences RNCP saturent les résultats | 🟢 corrigé | retrieval | q08 | `2026-10-02_01_e2e-prod-premier-test` |
| EC-05 | Le plafond par section coupe les réponses qui s'étalent sur plusieurs chunks | 🟢 corrigé | retrieval | q10 | `2026-10-02_23_e2e-prod-apres-pr5-pr6` |
| EC-06 | Une question générale se noie dans les cas particuliers | 🟠 atténué | retrieval | q07 | `2026-10-02_01_e2e-prod-premier-test` |
| EC-07 | Limites du modèle d'embedding | 🟠 atténué | embedding-model | q08, q16, c02.3 | `2026-10-02_22_retrieval-final-pr5` |
| EC-08 | Un préfixe long dégrade la recherche | 📘 enseignement | chunking | q10, q14 | `2026-10-02_06_retrieval-prefixe-long-k5` |
| EC-09 | Les fiches « clé : valeur » sont mal appariées aux questions | 🟢 corrigé | embedding-model | q03, q05, q06 | `2026-10-02_13_retrieval-300-prefixe-court-k10-cap1` |
| EC-10 | Angles morts de l'évaluation | 🟢 corrigé | eval-tooling | q03, q04, q13 | `2026-10-02_22_retrieval-final-pr5` |
| EC-11 | Erreurs dans les contenus du site Ynov | 🔴 ouvert | source-data |  | — |
| EC-12 | Les questions sur d'autres écoles passent le seuil | 🟢 corrigé | grading | q19, q26 | `2026-10-02_28_calibration-seuil-0-45` |
| EC-13 | Le LLM invente une règle générale à partir de quelques exemples | 🟢 corrigé | generation | q16 | `2026-10-02_26_local-apres-prompt-seuil` |
| EC-14 | Un chunk sépare des chiffres du titre auquel ils se rapportent | 🟢 corrigé | chunking | q15 | `2026-10-02_34_local-e5-large-300` |
| EC-15 | Le fichier d'exemple fictif est indexé en prod | 🟢 corrigé | source-data | q07, q09 | `2026-10-02_34_local-e5-large-300` |
| EC-16 | Les salutations et les remerciements sont refusés | 🔴 ouvert | grading | c07.2, c08.1 | `2026-10-03_04_local-conversations-jeu-c2` |
| EC-17 | Le fait cherché est dans la section récupérée, mais pas dans les chunks transmis | 🟠 atténué | retrieval | q07, q11, q28 | `2026-10-05_01_contexte-reference` |
| EC-18 | Le critère « bonne section récupérée » surestime la recherche | 🟢 corrigé | eval-tooling | q07, q10, q11 | `2026-10-05_01_contexte-reference` |

### EC-01 — Les embeddings ne lisent que 128 tokens

**Statut** : 🟢 corrigé · **Catégorie** : chunking · **Liens** : PR #5

- **Symptôme** : Aucune question de lieu ou de durée ne retrouvait la section « Infos clés », même avec 10 résultats (runs 02 à 09). En prod (run 01), « Dans quelles villes est proposé le Mastère IA ? » répondait « le contexte ne contient pas d'information ».
- **Preuve** : Le tokenizer de paraphrase-multilingual-MiniLM-L12-v2 tronque à 128 tokens. Avec des chunks de 500 caractères, plus de la moitié étaient tronqués (médiane 125 tokens, 90e centile 128). Le chunk « Infos clés » du Mastère IA s'arrêtait à « … 11 villes (campus Ynov) : Aix-en-Provence, Bordeaux » : le reste n'était jamais vectorisé.
- **Cause** : Taille des chunks (500 caractères) inadaptée à la fenêtre du modèle.
- **Correction** : Chunks de 300 caractères (1 % tronqués), constante unique CHUNK_SIZE dans ingestion/chunking.py. q02 passe au rang 1 (run 22), réponse correcte en prod (run 23).

### EC-02 — Question refusée à 0,003 du seuil de pertinence

**Statut** : 🟢 corrigé · **Catégorie** : grading · **Liens** : fix/prompt-and-threshold

- **Symptôme** : « Quelle est l'adresse e-mail du référent handicap de Lyon ? » est refusée en prod (« Je n'ai pas trouvé d'information pertinente », 0,2 s, aucune source), alors que la bonne section (handicap.html / Contact) est récupérée au rang 2.
- **Preuve** : Meilleur score 0,497 pour un seuil GRADE_THRESHOLD = 0,5 : le nœud grade refuse avant d'appeler le LLM. La réponse (handicap-lyon@ynov.com) est pourtant dans le contexte. Calibration (passage 28, jeu v5) : les 16 questions légitimes ont un meilleur score entre 0,497 et 0,887 ; 8 questions sans rapport (capitale, recette, météo, football…) entre 0,261 et 0,437.
- **Cause** : Seuil fixé à 0,5 sans calibration ; le passage à des chunks plus courts (EC-01) a déplacé la distribution des scores. L'évaluation de la recherche ne modélisait pas le seuil, d'où l'angle mort (voir EC-10).
- **Correction** : Seuil abaissé à 0,45 : 0 question légitime refusée et 8/8 questions sans rapport refusées (passage 28). Placé plus près des questions sans rapport (marge 0,013) que de la plus faible question légitime (marge 0,047), car refuser une vraie question coûte plus cher que laisser le LLM décliner une question hors sujet. q13 correcte en local (passages 26-27) puis en prod (passage 29). À recalibrer avec eval/retrieval.py si le découpage ou le modèle d'embedding changent. Recalibrage du 2026-10-05 (lot 3, #14) : les sections de module, plus ciblées, ont fait monter la question hors sujet la plus forte à 0,462 (q23) au-dessus de 0,45 ; seuil passé à 0,47 (marges 0,008 et 0,022, écart +0,030).

### EC-03 — Le LLM préfère une note de bas de page à l'information de lieu

**Statut** : 🟢 corrigé · **Catégorie** : generation · **Liens** : fix/prompt-and-threshold

- **Symptôme** : « Le Mastère Game Programmer est-il proposé à Lyon ? » → « Oui, à Lyon en contrat de professionnalisation ». Faux : la formation est 100 % en ligne.
- **Preuve** : Run 01 : la section de lieu n'était pas récupérée (EC-01). Run 23 : les 10 chunks transmis portent tous « (2 ans, 100 % en ligne, aucun campus) » dans leur en-tête, et le LLM donne toujours la même réponse fausse. Il s'appuie sur la note commune « contrat de professionnalisation … uniquement accessibles à Nice-Sophia, Aix, Lyon, … et Connect » de la section « Voies d'accès ».
- **Cause** : Le prompt ne dit pas que l'en-tête de chaque source (durée, lieux) fait foi ; la note générique est lue comme une information propre à la formation. « Lyon » n'apparaît pas dans le chunk « Lieux » d'une formation en ligne (score plafonné à 0,54).
- **Correction** : Règles 2 et 3 du prompt : l'en-tête « Formation (durée, lieux) » fait foi, et un passage commun à toutes les formations ne signifie pas qu'une formation donnée y est proposée. q03 correcte en local (passages 26-27) et en prod (passage 29) : « Non, 100 % en ligne, sans aucun campus » ; le LLM précise que la note sur les contrats de professionnalisation ne s'applique pas.

### EC-04 — Les tableaux d'équivalences RNCP saturent les résultats

**Statut** : 🟢 corrigé · **Catégorie** : retrieval · **Liens** : PR #5

- **Symptôme** : « Quels sont les blocs de compétences du titre Expert en cybersécurité ? » : les 5 sources récupérées venaient toutes de « Certifications professionnelles enregistrées au RNCP en correspondance partielle » (scores 0,891 à 0,901) ; aucune section de bloc.
- **Preuve** : Ces tableaux répètent les intitulés de blocs d'autres titres, très proches de la question. Réponse : 2 blocs sur 4.
- **Cause** : Sections d'équivalences peu utiles et très similaires aux questions de compétences.
- **Correction** : Sections d'équivalences et références légales retirées des fiches RNCP. Le problème restant (1 bloc sur 4, runs 22 et 23) relève du modèle d'embedding (EC-07). Lot 3 (#14) : section de synthèse « Blocs de compétences » par titre (liste des intitulés, en question-réponse). Passage 2026-10-05_06 : q08 et q27 correctes avec les 4 blocs.

### EC-05 — Le plafond par section coupe les réponses qui s'étalent sur plusieurs chunks

**Statut** : 🟢 corrigé · **Catégorie** : retrieval

- **Symptôme** : « Quels modules sont enseignés en Mastère 2 du Mastère IA ? » → un seul module cité (Intelligence artificielle avancée) sur trois.
- **Preuve** : Avec des chunks de 300 caractères, la section « Programme du Mastère » compte une vingtaine de chunks ; MAX_PER_SECTION = 2 n'en laisse passer que deux.
- **Cause** : Compromis introduit par PR #5 : le plafond diversifie les sources (utile pour q08, EC-04) mais pénalise les longues sections.
- **Correction** : À faire : une section par module (« Programme — Mastère 2 — Module 1 ») pour que le plafond s'applique par module ; à mesurer avec eval/retrieval.py et eval/e2e.py. Lot 3 (#14) : une section par année et module (« Programme du Mastère — Mastère 2 — Module 1 »), le plafond s'applique par module. Passage 2026-10-05_06 : q10 et q28 correctes.

### EC-06 — Une question générale se noie dans les cas particuliers

**Statut** : 🟠 atténué · **Catégorie** : retrieval · **Liens** : fix/prompt-and-threshold

- **Symptôme** : « Peut-on payer les frais de scolarité en plusieurs fois ? » → « oui », mais la réponse liste des tarifs de BTS et omet les règles générales (4 échéances, remise de 500 € au comptant), et conclut en prod (run 23) que c'est « probablement » possible partout.
- **Preuve** : Le document commun (Modalités de paiement) est récupéré (rang 3 ou 4), noyé parmi les sections Tarifs de chaque formation. Après la règle 4 du prompt (passages 26-27), la réponse annonce bien la règle commune mais toujours sans détails : le seul chunk récupéré de la section « Modalités de paiement » est le n°3 (formation continue, score 0,510), pas celui qui contient les 4 échéances et la remise de 500 €.
- **Cause** : D'abord le prompt (pas de priorité à l'information générale), corrigé par la règle 4 ; reste un problème de recherche : le bon chunk de la section commune n'est pas récupéré.
- **Correction** : Fait : règle 4 du prompt (règle commune d'abord, avec ses détails). À faire : faire remonter le bon chunk (garder les règles de paiement dans un seul chunk, ou meilleur modèle d'embedding, voir EC-07).

### EC-07 — Limites du modèle d'embedding

**Statut** : 🟠 atténué · **Catégorie** : embedding-model · **Liens** : feat/embedding-model-comparison

- **Symptôme** : Après PR #5, deux questions échouent encore en recherche : les blocs Cybersécurité (1 section de bloc sur 3 attendues) et « Quels BTS sont accessibles via Parcoursup ? » (la section Parcoursup de la page Admission n'est jamais récupérée, les pages BTS passent devant).
- **Preuve** : paraphrase-multilingual-MiniLM-L12-v2 est un petit modèle de paraphrase (384 dimensions, 128 tokens). Comparaison du 2026-10-02 (passages 30 à 34, mêmes 24 questions) : MiniLM 14/16 en recherche, écart de seuil +0,060, index en 167 s, recherche 9 ms ; mpnet 12/16, aucun seuil possible (écart -0,018), 593 s ; e5-large (chunks de 300) 15/16, q16 au rang 1, 9 questions sur 16 au rang 1 (5 pour MiniLM), mais écart de seuil de +0,023 seulement (tous les scores entre 0,75 et 0,92), index en 36 min (13 fois plus lent), recherche 69 ms ; e5-large (chunks de 500) 15/16 mais aucun seuil possible (-0,016). De bout en bout avec e5-large 300 (passage 34) : 12/16 correctes comme MiniLM en prod (passage 29), q16 corrigée mais q15 devenue fausse (EC-14). Après les corrections EC-14 et EC-15 (passages 35 à 38, corpus de 6 470 chunks) : recherche MiniLM 14/16 (6 questions au rang 1, écart +0,055, 172 s) contre e5-large 15/16 (11 au rang 1, écart +0,020, 1 905 s) ; de bout en bout, MiniLM 12/16 en prod contre e5-large 13/16 en local (q16 corrigée), aucune réponse fausse pour les deux. Même limite en conversation (passage 2026-10-03_04) : « Quel niveau faut-il pour entrer au BTS ERA ? » ramène « modalités d'évaluations certificatives » au lieu de « Infos clés », avec ou sans historique.
- **Cause** : Capacité du modèle.
- **Correction** : e5-large est désormais meilleur de bout en bout (+1 question, q16) mais coûte cher : ingestion d'environ 38 min sur le serveur (4 cœurs), environ 2,5 Go de RAM par processus sur 7,8 Go, recherche 71 ms au lieu de 9 ms, et un seuil fragile (écart +0,020). Décision à prendre ; q08 (blocs Cybersécurité) reste partielle avec les deux modèles. Lot 3 : q08 corrigée sans changer de modèle (EC-04). Restent q16 (Parcoursup) et q32 / c02.3 (niveau d'entrée du BTS ERA), visées par la recherche hybride (lot 4). Lot 4 (#14) : recherche hybride (BM25 français de FastEmbed, deux résultats injectés aux dernières places, score = cosinus). Passage 2026-10-06_01 : 22/22 questions avec tous les faits dans le contexte, q16 et q32 au rang 9, sans changer de modèle ; bout en bout local (passage 02) : q16 et q32 correctes ; conversation c02.3 correcte (passage 03). Reste la décision sur e5-large, à clore à la mise en production (lot 7) si la préprod atteint l'objectif avec MiniLM.

### EC-08 — Un préfixe long dégrade la recherche

**Statut** : 📘 enseignement · **Catégorie** : chunking · **Liens** : PR #5

- **Symptôme** : Mettre la liste complète des campus dans le préfixe de chaque chunk a fait baisser le score de 9/16 à 7/16 (5 résultats) : q10 et q14 ont été perdues.
- **Preuve** : Le préfixe consommait une grande part des 128 tokens (EC-01) et rendait tous les chunks d'une formation très similaires entre eux.
- **Cause** : Préfixe trop long pour la fenêtre du modèle.
- **Correction** : Approche abandonnée au profit d'un préfixe compact (« 2 ans, 11 campus et en ligne ») ; la liste complète reste dans la section « Lieux ».

### EC-09 — Les fiches « clé : valeur » sont mal appariées aux questions

**Statut** : 🟢 corrigé · **Catégorie** : embedding-model · **Liens** : PR #5

- **Symptôme** : Même sans troncature, le chunk « Infos clés » restait mal classé : 54e pour la question Game Programmer / Lyon, 31e pour le BTS ERA.
- **Preuve** : Score de la question « Où peut-on suivre le Mastère Game Programmer ? » : 0,52 contre la fiche « Durée : 2 ans … », 0,68 contre une formulation question + réponse.
- **Cause** : Modèle entraîné sur des paraphrases : il rapproche mieux une question d'une question que d'une liste de valeurs.
- **Correction** : « Infos clés » rédigées en questions-réponses et nouvelle section « Lieux ». q06 passe au rang 1, q05 au rang 6.

### EC-10 — Angles morts de l'évaluation

**Statut** : 🟢 corrigé · **Catégorie** : eval-tooling · **Liens** : PR #5, feat/eval-reporting

- **Symptôme** : (a) Le critère « bonne section récupérée » comptait q03/q04 en échec alors que « 100 % en ligne » arrivait au LLM par l'en-tête de chaque chunk. (b) L'évaluation ne modélisait pas le seuil de pertinence : q13 passait en local mais était refusée en prod (EC-02). (c) Une bonne recherche ne garantit pas une bonne réponse (EC-03).
- **Preuve** : Écarts entre le run 22 (recherche, 14/16) et le run 23 (prod, 10/16 correctes). Ensuite, la vérification automatique des réponses s'est trompée dans les deux sens : (d) faux positif sur q16 au passage 26 (réponse inventée jugée correcte car elle citait les 3 BTS attendus) ; (e) faux négatif sur q26 au passage 25 (« ne sont pas mentionnées » non reconnu comme un refus).
- **Cause** : Évaluation limitée à la recherche, sans seuil ni contrôle des réponses.
- **Correction** : (a) critère expect_text (jeu de questions v3) ; (b) top_score et refused_by_threshold enregistrés par eval/retrieval.py ; (c) eval/e2e.py vérifie les réponses du LLM (answer_must / answer_must_not) et enregistre un verdict ; (d) answer_must_not sur q16 ; (e) formulations de refus élargies. Les verdicts automatiques restent à relire.

### EC-11 — Erreurs dans les contenus du site Ynov

**Statut** : 🔴 ouvert · **Catégorie** : source-data · **Liens** : PR #1

- **Symptôme** : (1) La page Bachelor Informatique contient une section « Voie d'accès » copiée depuis Architecture d'intérieur (« diplôme de niveau 5 … dans le domaine de l'architecture d'intérieur »). (2) La page Mastère Expert en jumeaux numériques contient une note interne publiée : « Formulation à recaler sur le référentiel officiel avec l'équipe certification. »
- **Preuve** : Relevé lors du scraping des 42 formations (PR
- **Cause** : Contenu source.
- **Correction** : À signaler à Ynov ; le RAG restitue ces contenus tels quels.

### EC-12 — Les questions sur d'autres écoles passent le seuil

**Statut** : 🟢 corrigé · **Catégorie** : grading · **Liens** : fix/prompt-and-threshold

- **Symptôme** : « Quels sont les frais de scolarité de HEC Paris ? » et « Quelles sont les conditions d'admission à Polytechnique ? » ne peuvent pas être filtrées par le seuil.
- **Preuve** : Meilleurs scores 0,609 (HEC → une section Tarifs Ynov) et 0,593 (Polytechnique), au milieu des questions légitimes (0,497 à 0,887) : aucun seuil ne les sépare. Avant la correction (passage 25), le LLM déclinait déjà ces deux questions de lui-même.
- **Cause** : Le vocabulaire (frais, admission) est le même que celui des questions Ynov.
- **Correction** : Préventif : règle 5 du prompt (ne répondre que sur Ynov). Passages 26-27 : « Je ne peux répondre qu'aux questions sur Ynov Campus. » Suivi par q19 et q26 (out_of_scope: llm).

### EC-13 — Le LLM invente une règle générale à partir de quelques exemples

**Statut** : 🟢 corrigé · **Catégorie** : generation · **Liens** : fix/prompt-and-threshold

- **Symptôme** : Avec le premier nouveau prompt, « Quels BTS sont accessibles via Parcoursup ? » → liste 5 BTS dont Communication et NDRC, et affirme « Tous les BTS Ynov sont post-bac et donc éligibles à Parcoursup ». Faux : seuls CIEL, SIO SLAM et SIO SISR le sont (page Admission). Avant, le LLM répondait honnêtement qu'il ne savait pas.
- **Preuve** : Passage 25 (prompt d'origine) : « sans réponse » ; passage 26 (prompt v1) : réponse fausse et assurée ; passage 27 (prompt v2) : de nouveau « sans réponse ». Le contexte ne contient que des pages BTS (la section Parcoursup n'est pas récupérée, EC-07).
- **Cause** : Les nouvelles règles poussent le LLM à répondre de façon générale ; sans contexte suffisant, il a généralisé au lieu de s'abstenir.
- **Correction** : Fin de la règle 1 du prompt : aucune déduction ni généralisation qui n'est pas écrite dans le contexte. Contrôle automatique renforcé (q16 answer_must_not). La vraie correction de q16 reste la recherche (EC-07).

### EC-14 — Un chunk sépare des chiffres du titre auquel ils se rapportent

**Statut** : 🟢 corrigé · **Catégorie** : chunking · **Liens** : PR #12

- **Symptôme** : Avec e5-large, « Quel est le taux de réussite du titre Expert en développement logiciel ? » → « 79 %, 121 certifiés sur 154 » : ce sont les chiffres des apprentis du titre Expert en cybersécurité. La bonne réponse est 76 % (77 % pour les apprentis).
- **Preuve** : La page CFA liste les taux par titre (nom du titre, puis 4 lignes de chiffres). Le chunk récupéré commence par les dernières lignes du titre Cybersécurité (« 79 % … 121 sur 154 ») et finit sur le nom du titre suivant, « Expert en Développement Logiciel ». Le préfixe ne donne que la section (« Taux de réussite apprentis »), pas le titre RNCP.
- **Cause** : Découpage à 300 caractères au milieu d'une liste dont chaque groupe dépend d'un titre ; MiniLM ne récupérait pas ce chunk, e5-large si.
- **Correction** : Les blocs des pages d'information qui ont au moins deux sous-titres h3 sont découpés en une section par sous-titre (« Taux de réussite apprentis — Expert en Développement Logiciel – [RNCP39583] »), ce qui profite aussi aux FAQ et aux coordonnées par campus. Avec e5-large (passage 38), q15 est correcte : 76 % pour le titre, 77 % pour les apprentis ; avec MiniLM en prod (passage 35), toujours 76 %.

### EC-15 — Le fichier d'exemple fictif est indexé en prod

**Statut** : 🟢 corrigé · **Catégorie** : source-data · **Liens** : PR #11

- **Symptôme** : Avec e5-large, la réponse à « Peut-on payer en plusieurs fois ? » ajoute « 1, 3 ou 10 mensualités sans frais » : cette information n'existe pas sur le site Ynov.
- **Preuve** : Elle vient de data/samples/admissions_faq.md, un exemple créé avec le squelette du projet (commit 9628924) : Mastère à 10 200 €, paiement en 10 mensualités, admissions@ynov.com, 01 40 79 00 00… Il est ingéré en prod depuis la première ingestion (doc_type faq) et remontait déjà parmi les sources de q09 au premier test (passage 01).
- **Cause** : data/samples/ est ingéré comme le reste du corpus.
- **Correction** : Le fichier est déplacé dans tests/fixtures/ (fixture des tests du loader Markdown, marquée fictive), data/ est entièrement exclu de git et de l'image, le dossier est supprimé du serveur et la réingestion a retiré ses points de l'index (synchronisation de l'indexeur). Aucune source ne le cite plus aux passages 35 et 38.

### EC-16 — Les salutations et les remerciements sont refusés

**Statut** : 🔴 ouvert · **Catégorie** : grading

- **Symptôme** : « Bonjour » en début de conversation et « Merci beaucoup ! » après une réponse reçoivent « Je n'ai pas trouvé d'information pertinente dans les documents Ynov pour répondre à votre question. ».
- **Preuve** : Passage 04 du 2026-10-03 (scénarios c07 et c08) : les deux sont refusés par le seuil. « Bonjour » sans appel du LLM ; « Merci beaucoup ! » reste inchangé après reformulation. Même résultat avec « D'accord, super. » à la main.
- **Cause** : Le seuil compare la question aux chunks du corpus ; une formule de politesse ne ressemble à aucun chunk. Sans effet dans l'API à une question, gênant dans un chat.
- **Correction** : Prévu dans le chantier #14 (abandonné le 2026-10-04, repris le même jour). Piste : repérer les messages de politesse avant la recherche (règles simples ou appel LLM) et répondre en une phrase, en rappelant ce que l'assistant sait faire. À mesurer avec les scénarios c07 et c08.

### EC-17 — Le fait cherché est dans la section récupérée, mais pas dans les chunks transmis

**Statut** : 🟠 atténué · **Catégorie** : retrieval

- **Symptôme** : q11 (« Comment se passe l'entretien d'admission ? ») : réponse sans la durée d'1 h alors que la section « Le rendez-vous d'admission » est récupérée au rang 1. q07 : les « 4 échéances » et la remise de 500 € manquent, q28 : aucun des modules attendus.
- **Preuve** : Passage 2026-10-05_01 (corpus complet, MiniLM) : q07 0/2 faits dans le contexte, q11 1/2, q28 0/2, alors que le critère « bonne section » les compte réussies. Pour q11 le chunk « Durée : 1h » (chunk 0 de la section) est au 21e rang, pour q07 le chunk « 4 échéances » au 16e. Simulation sans LLM : envoyer la section entière (si elle fait au plus 2 000 caractères) au lieu des seuls chunks retrouvés remet ces faits dans le contexte.
- **Cause** : Les sections sont coupées en chunks de 300 caractères, le LLM ne reçoit que ceux qui ressemblent à la question, pas le reste de leur section.
- **Correction** : Lot 2 (chantier #14) : chaque chunk d'une section de 2 000 caractères au plus porte le texte entier de la section (`section_text`) et le LLM reçoit la section, une fois, au lieu des chunks retrouvés. Passage 2026-10-05_02 : 16/22 questions avec tous leurs faits dans le contexte (14 avant), q07 et q11 corrigées ; de bout en bout (passage 03) q11 correcte. Reste les sections plus longues (q28 : programme d'un Bachelor), voir EC-05. Lot 3 : les programmes sont découpés par module, ce qui rend q28 correcte.

### EC-18 — Le critère « bonne section récupérée » surestime la recherche

**Statut** : 🟢 corrigé · **Catégorie** : eval-tooling · **Liens** : feat/eval-context-facts

- **Symptôme** : La recherche affichait 14/16 (CI) alors que le bout en bout en donnait 11/16 : q07, q10 et q11 passaient en recherche et échouaient dans les réponses.
- **Preuve** : Passage 2026-10-05_01 : 18/22 sections trouvées, mais 14/22 questions dont tous les faits attendus sont dans le contexte envoyé au LLM.
- **Cause** : Le contrôle ne regardait que la section d'origine des chunks, pas leur contenu.
- **Correction** : eval/retrieval.py lit le contexte construit par graph.nodes.generate.build_context et cherche les faits attendus (`context_must`, sinon `answer_must`) ; la référence de la CI suit aussi `context_ok`. Jeu de questions v8, avec six questions de contrôle (q27 à q32).

## Ajouter un passage

```sh
uv run python -m eval.retrieval --save "libellé"   # recherche, en local
uv run python -m eval.e2e --save "libellé"         # réponses de l'API (prod)
uv run python -m eval.report                       # régénère ce rapport
```

Après un test de bout en bout, relire les verdicts automatiques dans le JSON (`verdict`, `review_note`, `edge_cases`) et passer `milestone` à `true` pour les étapes à suivre dans la matrice.
