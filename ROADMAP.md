# Roadmap

Plan du projet RAG Ynov. Chaque chantier est suivi dans une issue GitHub (label `roadmap`), qui contient le détail des tâches, les critères de fin et les dépendances. Ce fichier donne la vue d'ensemble ; l'avancement se lit dans les issues.

## Où en est le projet (2 octobre 2026)

- **Corpus** : 42 formations ynov.com, 7 pages d'information, un document des règles communes et 29 fiches RNCP actives, soit 6 470 chunks.
- **Qualité en prod** : 12 réponses correctes sur 16 questions de référence, aucune réponse fausse, 10 questions hors sujet sur 10 écartées (`eval/results/2026-10-02_35_prod-apres-ec14-ec15.json`).
- **Suivi** : chaque test est enregistré dans `eval/results/`, chaque anomalie documentée dans `eval/edge_cases.yaml` ; synthèse dans `eval/REPORT.md`.

## Chantiers

| # | Chantier | Domaine | Dépend de |
|---|---|---|---|
| [#14](https://github.com/Romain-Data/RAG-ynov/issues/14) | Améliorer la qualité des réponses | qualité | — |
| [#15](https://github.com/Romain-Data/RAG-ynov/issues/15) | Mettre en place l'intégration continue | infra | — |
| [#16](https://github.com/Romain-Data/RAG-ynov/issues/16) | Tableau de bord de l'évolution des résultats | produit | #18, #19 (pour les indicateurs d'usage) |
| [#17](https://github.com/Romain-Data/RAG-ynov/issues/17) | Interface utilisateur de chat | produit | #14 (liens vers les sources) |
| [#18](https://github.com/Romain-Data/RAG-ynov/issues/18) | Journal des réponses pour la revue manuelle | produit | — |
| [#19](https://github.com/Romain-Data/RAG-ynov/issues/19) | Bouton « réponse satisfaisante ou non » | produit | #17, #18 |
| [#20](https://github.com/Romain-Data/RAG-ynov/issues/20) | Rapport des questions sans réponse | produit | #18 |
| [#21](https://github.com/Romain-Data/RAG-ynov/issues/21) | Rafraîchissement automatique du corpus et suivi des versions | données | — |

## Ordre suggéré

1. **#15 Intégration continue** : protège tout le reste, chaque PR est vérifiée avant le merge.
2. **#14 Qualité des réponses** et **#21 Rafraîchissement du corpus** : peuvent avancer en parallèle. #21 apporte les versions du corpus, utiles pour comparer les résultats dans le temps.
3. **#18 Journal des réponses** : la base de #19, #20 et des indicateurs d'usage de #16.
4. **#17 Interface utilisateur**, puis **#19 Bouton d'avis**.
5. **#20 Rapport des questions sans réponse** et **#16 Tableau de bord**, quand le journal contient assez de données.

## Comment avancer sur un chantier

- Une branche par sujet, jamais de commit sur `main` : `feat/…`, `fix/…`, `chore/…`.
- Dans la description de la PR, écrire `Closes #N` : l'issue se ferme automatiquement au merge.
- Pour tout changement qui touche la recherche ou les réponses : mesurer avant et après avec `eval/retrieval.py` et `eval/e2e.py`, enregistrer les passages et mettre à jour les cas limites concernés.
