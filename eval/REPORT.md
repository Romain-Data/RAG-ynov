# Rapport d'évaluation du RAG

> Généré par `uv run python -m eval.report` à partir de `eval/results/*.json` et `eval/edge_cases.yaml` : ne pas modifier à la main.

## Synthèse

- **Dernier test de bout en bout** (prod, `2026-10-02_29_prod-apres-prompt-seuil`) : 12/16 ✅ · 3 🟡 · 0 ❌ · hors périmètre 10/10 ; 0 refusée(s), 1 sans réponse.
- **Dernière évaluation de la recherche** (`2026-10-02_28_calibration-seuil-0-45`) : 14/16 · hors périmètre 8/8 ⛔.
- **Cas limites** : 13 documentés, dont 5 ouverts ou atténués (EC-04, EC-05, EC-06, EC-07, EC-11).

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

## Matrice par question (étapes clés)

Recherche : ✅ rang de la bonne section · ✅ ctx = fait présent dans le contexte · ❌ absente · (d/m) sections distinctes / requises · ⛔ refusée par le seuil. Bout en bout : ✅ correct · 🟡 partial · ❌ wrong · ⛔ refused · ∅ no_answer · ⚠️ error.

| Question | 01 e2e | 02 ret | 04 ret | 06 ret | 10 ret | 22 ret | 23 e2e | 25 e2e | 27 e2e | 28 ret | 29 e2e |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **q01** Combien coûte le Mastère Expert en intelligence artificielle | ✅ | ✅ 2 | ✅ 2 | ✅ 2 | ✅ 2 | ✅ 2 | ✅ | ✅ | ✅ | ✅ 2 | ✅ |
| **q02** Dans quelles villes est proposé le Mastère Expert en intelli | ∅ | ❌ | ❌ | ❌ | ❌ | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ |
| **q03** Le Mastère Game Programmer est-il proposé à Lyon ? | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ ctx | ❌ | ❌ | ✅ | ✅ ctx | ✅ |
| **q04** Le Mastère Expert en cybersécurité - Pentester se fait-il en | · | ❌ | ❌ | ❌ | ❌ | ✅ ctx | ✅ | ✅ | ✅ | ✅ ctx | ✅ |
| **q05** Où peut-on suivre le BTS ERA ? | · | ❌ | ✅ 7 | ❌ | ❌ | ✅ 6 | ✅ | ✅ | ✅ | ✅ 6 | ✅ |
| **q06** Combien de temps dure le Bachelor Informatique ? | · | ❌ | ❌ | ❌ | ❌ | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ |
| **q07** Peut-on payer les frais de scolarité en plusieurs fois ? | 🟡 | ✅ 3 | ✅ 3 | ✅ 3 | ✅ 4 | ✅ 4 | 🟡 | 🟡 | 🟡 | ✅ 4 | 🟡 |
| **q08** Quels sont les blocs de compétences du titre RNCP Expert en  | 🟡 | ❌ (0/3) | ❌ 8 (1/3) | ❌ 3 (1/3) | ❌ (0/3) | ❌ 8 (1/3) | 🟡 | 🟡 | 🟡 | ❌ 8 (1/3) | 🟡 |
| **q09** Quel est le numéro de téléphone du campus de Bordeaux ? | ✅ | ✅ 1 | ✅ 1 | ✅ 4 | ✅ 5 | ✅ 5 | ✅ | ✅ | ✅ | ✅ 5 | ✅ |
| **q10** Quels modules sont enseignés en Mastère 2 du Mastère Expert  | · | ✅ 1 | ✅ 1 | ❌ | ✅ 1 | ✅ 1 | 🟡 | 🟡 | 🟡 | ✅ 1 | 🟡 |
| **q11** Comment se passe l'entretien d'admission chez Ynov ? | · | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ |
| **q12** Combien coûte une VAE chez Ynov ? | · | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 1 | ✅ | ✅ | ✅ | ✅ 1 | ✅ |
| **q13** Quelle est l'adresse e-mail du référent handicap de Lyon ? | · | ✅ 1 | ✅ 1 | ✅ 1 | ✅ 2 | ✅ 2 ⛔ | ⛔ | ⛔ | ✅ | ✅ 2 | ✅ |
| **q14** Quels métiers peut-on exercer après le Mastère Data engineer | · | ✅ 1 | ✅ 1 | ❌ | ✅ 2 | ✅ 2 | ✅ | ✅ | ✅ | ✅ 2 | ✅ |
| **q15** Quel est le taux de réussite du titre Expert en développemen | · | ✅ 1 | ✅ 1 | ✅ 3 | ❌ | ✅ 6 | ✅ | ✅ | ✅ | ✅ 6 | ✅ |
| **q16** Quels BTS sont accessibles via Parcoursup ? | · | ❌ | ❌ | ❌ | ❌ | ❌ | ∅ | ∅ | ∅ | ❌ | ∅ |
| **q17** Quelle est la capitale de l'Australie ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q18** Donne-moi une recette de pâte à crêpes. | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q19** Quels sont les frais de scolarité de HEC Paris ? | · | · | · | · | · | · | · | ✅ | ✅ | · | ✅ |
| **q20** Quel temps fera-t-il demain à Lyon ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q21** Comment réparer une fuite d'eau sous un évier ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q22** Qui a gagné la Coupe du monde de football 2018 ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q23** Quel est le meilleur langage de programmation pour débuter ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q24** Peux-tu m'écrire un poème sur l'automne ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q25** Combien coûte un abonnement Netflix ? | · | · | · | · | · | · | · | ✅ | ✅ | ✅ None ⛔ | ✅ |
| **q26** Quelles sont les conditions d'admission à Polytechnique ? | · | · | · | · | · | · | · | ✅ | ✅ | · | ✅ |

Colonnes : `01` e2e-prod-premier-test · `02` retrieval-baseline-500-k5 · `04` retrieval-500-k10-cap2 · `06` retrieval-prefixe-long-k5 · `10` retrieval-300-prefixe-court-k5 · `22` retrieval-final-pr5 · `23` e2e-prod-apres-pr5-pr6 · `25` local-avant-prompt-seuil · `27` local-apres-prompt-v2 · `28` calibration-seuil-0-45 · `29` prod-apres-prompt-seuil

## Détail du dernier test de bout en bout (`2026-10-02_29_prod-apres-prompt-seuil`)

| Question | Verdict | Cas limites | Commentaire |
|---|---|---|---|
| **q01** Combien coûte le Mastère Expert en intelligence artific | ✅ correct |  |  |
| **q02** Dans quelles villes est proposé le Mastère Expert en in | ✅ correct |  |  |
| **q03** Le Mastère Game Programmer est-il proposé à Lyon ? | ✅ correct |  | Confirmé en prod : « Non… 100 % en ligne » (EC-03 corrigé). |
| **q04** Le Mastère Expert en cybersécurité - Pentester se fait- | ✅ correct |  |  |
| **q05** Où peut-on suivre le BTS ERA ? | ✅ correct |  |  |
| **q06** Combien de temps dure le Bachelor Informatique ? | ✅ correct |  |  |
| **q07** Peut-on payer les frais de scolarité en plusieurs fois  | 🟡 partial | EC-06 | « Oui, pour toutes les formations » puis des tarifs échelonnés de 5 formations ; ni les 4 échéances, ni la remise de 500 € (le chunk qui les contient n'est pas récupéré). |
| **q08** Quels sont les blocs de compétences du titre RNCP Exper | 🟡 partial | EC-07 | 1 bloc sur 4. |
| **q09** Quel est le numéro de téléphone du campus de Bordeaux ? | ✅ correct |  |  |
| **q10** Quels modules sont enseignés en Mastère 2 du Mastère Ex | 🟡 partial | EC-05 | 1 module sur 3. |
| **q11** Comment se passe l'entretien d'admission chez Ynov ? | ✅ correct |  | Description juste, avec le délai de 48 h ; ne cite pas la durée (1 h). |
| **q12** Combien coûte une VAE chez Ynov ? | ✅ correct |  |  |
| **q13** Quelle est l'adresse e-mail du référent handicap de Lyo | ✅ correct |  | Confirmé en prod : handicap-lyon@ynov.com, plus refusée par le seuil (EC-02 corrigé). |
| **q14** Quels métiers peut-on exercer après le Mastère Data eng | ✅ correct |  |  |
| **q15** Quel est le taux de réussite du titre Expert en dévelop | ✅ correct |  |  |
| **q16** Quels BTS sont accessibles via Parcoursup ? | ∅ no_answer | EC-07 | Répond honnêtement qu'il ne sait pas : la section Parcoursup n'est pas récupérée. |
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

### Fiabilité de la vérification automatique

Sur les réponses revues à la main, le verdict automatique (`answer_must`) concorde dans 117/126 cas. Désaccords :

- `2026-10-02_01_e2e-prod-premier-test` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_23_e2e-prod-apres-pr5-pr6` q11 : revue **correct**, automatique **wrong**
- `2026-10-02_25_local-avant-prompt-seuil` q11 : revue **correct**, automatique **wrong**
- `2026-10-02_26_local-apres-prompt-seuil` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_26_local-apres-prompt-seuil` q11 : revue **correct**, automatique **wrong**
- `2026-10-02_27_local-apres-prompt-v2` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_27_local-apres-prompt-v2` q11 : revue **correct**, automatique **partial**
- `2026-10-02_29_prod-apres-prompt-seuil` q07 : revue **partial**, automatique **wrong**
- `2026-10-02_29_prod-apres-prompt-seuil` q11 : revue **correct**, automatique **partial**

## Cas limites

| Id | Titre | Statut | Catégorie | Questions | Découvert dans |
|---|---|---|---|---|---|
| EC-01 | Les embeddings ne lisent que 128 tokens | 🟢 corrigé | chunking | q02, q05, q06 | `2026-10-02_09_retrieval-prefixe-long-k10-cap1` |
| EC-02 | Question refusée à 0,003 du seuil de pertinence | 🟢 corrigé | grading | q13 | `2026-10-02_23_e2e-prod-apres-pr5-pr6` |
| EC-03 | Le LLM préfère une note de bas de page à l'information de lieu | 🟢 corrigé | generation | q03 | `2026-10-02_01_e2e-prod-premier-test` |
| EC-04 | Les tableaux d'équivalences RNCP saturent les résultats | 🟠 atténué | retrieval | q08 | `2026-10-02_01_e2e-prod-premier-test` |
| EC-05 | Le plafond par section coupe les réponses qui s'étalent sur plusieurs chunks | 🔴 ouvert | retrieval | q10 | `2026-10-02_23_e2e-prod-apres-pr5-pr6` |
| EC-06 | Une question générale se noie dans les cas particuliers | 🟠 atténué | retrieval | q07 | `2026-10-02_01_e2e-prod-premier-test` |
| EC-07 | Limites du modèle d'embedding | 🔴 ouvert | embedding-model | q08, q16 | `2026-10-02_22_retrieval-final-pr5` |
| EC-08 | Un préfixe long dégrade la recherche | 📘 enseignement | chunking | q10, q14 | `2026-10-02_06_retrieval-prefixe-long-k5` |
| EC-09 | Les fiches « clé : valeur » sont mal appariées aux questions | 🟢 corrigé | embedding-model | q03, q05, q06 | `2026-10-02_13_retrieval-300-prefixe-court-k10-cap1` |
| EC-10 | Angles morts de l'évaluation | 🟢 corrigé | eval-tooling | q03, q04, q13 | `2026-10-02_22_retrieval-final-pr5` |
| EC-11 | Erreurs dans les contenus du site Ynov | 🔴 ouvert | source-data |  | — |
| EC-12 | Les questions sur d'autres écoles passent le seuil | 🟢 corrigé | grading | q19, q26 | `2026-10-02_28_calibration-seuil-0-45` |
| EC-13 | Le LLM invente une règle générale à partir de quelques exemples | 🟢 corrigé | generation | q16 | `2026-10-02_26_local-apres-prompt-seuil` |

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
- **Correction** : Seuil abaissé à 0,45 : 0 question légitime refusée et 8/8 questions sans rapport refusées (passage 28). Placé plus près des questions sans rapport (marge 0,013) que de la plus faible question légitime (marge 0,047), car refuser une vraie question coûte plus cher que laisser le LLM décliner une question hors sujet. q13 correcte en local (passages 26-27) puis en prod (passage 29). À recalibrer avec eval/retrieval.py si le découpage ou le modèle d'embedding changent.

### EC-03 — Le LLM préfère une note de bas de page à l'information de lieu

**Statut** : 🟢 corrigé · **Catégorie** : generation · **Liens** : fix/prompt-and-threshold

- **Symptôme** : « Le Mastère Game Programmer est-il proposé à Lyon ? » → « Oui, à Lyon en contrat de professionnalisation ». Faux : la formation est 100 % en ligne.
- **Preuve** : Run 01 : la section de lieu n'était pas récupérée (EC-01). Run 23 : les 10 chunks transmis portent tous « (2 ans, 100 % en ligne, aucun campus) » dans leur en-tête, et le LLM donne toujours la même réponse fausse. Il s'appuie sur la note commune « contrat de professionnalisation … uniquement accessibles à Nice-Sophia, Aix, Lyon, … et Connect » de la section « Voies d'accès ».
- **Cause** : Le prompt ne dit pas que l'en-tête de chaque source (durée, lieux) fait foi ; la note générique est lue comme une information propre à la formation. « Lyon » n'apparaît pas dans le chunk « Lieux » d'une formation en ligne (score plafonné à 0,54).
- **Correction** : Règles 2 et 3 du prompt : l'en-tête « Formation (durée, lieux) » fait foi, et un passage commun à toutes les formations ne signifie pas qu'une formation donnée y est proposée. q03 correcte en local (passages 26-27) et en prod (passage 29) : « Non, 100 % en ligne, sans aucun campus » ; le LLM précise que la note sur les contrats de professionnalisation ne s'applique pas.

### EC-04 — Les tableaux d'équivalences RNCP saturent les résultats

**Statut** : 🟠 atténué · **Catégorie** : retrieval · **Liens** : PR #5

- **Symptôme** : « Quels sont les blocs de compétences du titre Expert en cybersécurité ? » : les 5 sources récupérées venaient toutes de « Certifications professionnelles enregistrées au RNCP en correspondance partielle » (scores 0,891 à 0,901) ; aucune section de bloc.
- **Preuve** : Ces tableaux répètent les intitulés de blocs d'autres titres, très proches de la question. Réponse : 2 blocs sur 4.
- **Cause** : Sections d'équivalences peu utiles et très similaires aux questions de compétences.
- **Correction** : Sections d'équivalences et références légales retirées des fiches RNCP. Le problème restant (1 bloc sur 4, runs 22 et 23) relève du modèle d'embedding (EC-07).

### EC-05 — Le plafond par section coupe les réponses qui s'étalent sur plusieurs chunks

**Statut** : 🔴 ouvert · **Catégorie** : retrieval

- **Symptôme** : « Quels modules sont enseignés en Mastère 2 du Mastère IA ? » → un seul module cité (Intelligence artificielle avancée) sur trois.
- **Preuve** : Avec des chunks de 300 caractères, la section « Programme du Mastère » compte une vingtaine de chunks ; MAX_PER_SECTION = 2 n'en laisse passer que deux.
- **Cause** : Compromis introduit par PR #5 : le plafond diversifie les sources (utile pour q08, EC-04) mais pénalise les longues sections.
- **Correction** : À faire : une section par module (« Programme — Mastère 2 — Module 1 ») pour que le plafond s'applique par module ; à mesurer avec eval/retrieval.py et eval/e2e.py.

### EC-06 — Une question générale se noie dans les cas particuliers

**Statut** : 🟠 atténué · **Catégorie** : retrieval · **Liens** : fix/prompt-and-threshold

- **Symptôme** : « Peut-on payer les frais de scolarité en plusieurs fois ? » → « oui », mais la réponse liste des tarifs de BTS et omet les règles générales (4 échéances, remise de 500 € au comptant), et conclut en prod (run 23) que c'est « probablement » possible partout.
- **Preuve** : Le document commun (Modalités de paiement) est récupéré (rang 3 ou 4), noyé parmi les sections Tarifs de chaque formation. Après la règle 4 du prompt (passages 26-27), la réponse annonce bien la règle commune mais toujours sans détails : le seul chunk récupéré de la section « Modalités de paiement » est le n°3 (formation continue, score 0,510), pas celui qui contient les 4 échéances et la remise de 500 €.
- **Cause** : D'abord le prompt (pas de priorité à l'information générale), corrigé par la règle 4 ; reste un problème de recherche : le bon chunk de la section commune n'est pas récupéré.
- **Correction** : Fait : règle 4 du prompt (règle commune d'abord, avec ses détails). À faire : faire remonter le bon chunk (garder les règles de paiement dans un seul chunk, ou meilleur modèle d'embedding, voir EC-07).

### EC-07 — Limites du modèle d'embedding

**Statut** : 🔴 ouvert · **Catégorie** : embedding-model

- **Symptôme** : Après PR #5, deux questions échouent encore en recherche : les blocs Cybersécurité (1 section de bloc sur 3 attendues) et « Quels BTS sont accessibles via Parcoursup ? » (la section Parcoursup de la page Admission n'est jamais récupérée, les pages BTS passent devant).
- **Preuve** : paraphrase-multilingual-MiniLM-L12-v2 est un petit modèle de paraphrase (384 dimensions, 128 tokens), faible pour rapprocher une question d'un passage.
- **Cause** : Capacité du modèle.
- **Correction** : Prévu : comparer avec intfloat/multilingual-e5-large (512 tokens) via eval/retrieval.py, en tenant compte du coût (modèle de 2,2 Go, ingestion et requêtes plus lentes).

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

## Ajouter un passage

```sh
uv run python -m eval.retrieval --save "libellé"   # recherche, en local
uv run python -m eval.e2e --save "libellé"         # réponses de l'API (prod)
uv run python -m eval.report                       # régénère ce rapport
```

Après un test de bout en bout, relire les verdicts automatiques dans le JSON (`verdict`, `review_note`, `edge_cases`) et passer `milestone` à `true` pour les étapes à suivre dans la matrice.
