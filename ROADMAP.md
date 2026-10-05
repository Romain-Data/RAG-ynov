# Roadmap

Plan du projet RAG Ynov. Chaque chantier est suivi dans une issue GitHub (label `roadmap`), qui contient le détail des tâches, les critères de fin et les dépendances. Ce fichier donne la vue d'ensemble ; l'avancement se lit dans les issues.

## Où en est le projet (5 octobre 2026)

- **Corpus** : 42 formations ynov.com, 7 pages d'information, un document des règles communes et 29 fiches RNCP actives, soit 6 470 chunks.
- **Qualité en prod** : 11 réponses correctes sur 16 questions de référence, aucune réponse fausse, 10 questions hors sujet sur 10 écartées (`eval/results/2026-10-04_05_preprod-mammouth-recommended.json`, préprod au même code et au même modèle que la prod). C'était 12/16 avec l'ancien modèle (`2026-10-02_35`) : q11 et q07 ont reculé.
- **LLM** : `mammouth-recommended` en prod et en préprod depuis le 4 octobre 2026 (environ 11 fois moins cher que `mistral-medium-3-5` : 0,5 $ contre 5,6 $ pour 1 000 questions), alias de Mammouth dont le modèle sous-jacent peut changer.
- **Intégration continue** : en place (#15) ; une préprod protégée par mot de passe, évaluée avant chaque mise en production.
- **Suivi** : chaque test est enregistré dans `eval/results/`, chaque anomalie documentée dans `eval/edge_cases.yaml` ; synthèse dans `eval/REPORT.md`.

## Chantiers

| # | Chantier | Domaine | Dépend de |
|---|---|---|---|
| [#14](https://github.com/Romain-Data/RAG-ynov/issues/14) | Améliorer la qualité des réponses (dont EC-16, salutations et remerciements ; base de 11/16 depuis le changement de modèle) | qualité | — |
| [#15](https://github.com/Romain-Data/RAG-ynov/issues/15) | ~~Mettre en place l'intégration continue~~ **fait le 4 octobre 2026** (aucun appel au LLM sur les PR ; évaluation sur la préprod avant la mise en production) | infra | — |
| [#16](https://github.com/Romain-Data/RAG-ynov/issues/16) | Tableau de bord de l'évolution des résultats | produit | #18, #19 (pour les indicateurs d'usage) |
| [#17](https://github.com/Romain-Data/RAG-ynov/issues/17) | Interface utilisateur de chat (Chainlit, comptes, historique) : **en prod depuis le 3 octobre 2026** ; reste la limite de fréquence du chat, l'essai par un vrai compte, l'accessibilité | produit | #14 (liens vers les sources) |
| [#18](https://github.com/Romain-Data/RAG-ynov/issues/18) | Journal des réponses pour la revue manuelle | produit | — |
| [#19](https://github.com/Romain-Data/RAG-ynov/issues/19) | Bouton « réponse satisfaisante ou non » | produit | #17, #18 |
| [#20](https://github.com/Romain-Data/RAG-ynov/issues/20) | Rapport des questions sans réponse | produit | #18 |
| [#21](https://github.com/Romain-Data/RAG-ynov/issues/21) | Rafraîchissement automatique du corpus et suivi des versions | données | — |

## Interface de chat (#17) : décisions du 3 octobre 2026

- **Technologie : [Chainlit](https://docs.chainlit.io)**, monté dans l'API FastAPI actuelle. Agent Chat UI a été écarté : il impose un serveur LangGraph (Aegra), PostgreSQL et un front Next.js, soit trois services de plus. Un prototype Chainlit a validé la connexion, l'historique, la reprise d'une conversation et le cloisonnement entre comptes.
- **Connexion obligatoire, pseudo + mot de passe uniquement** (hachage argon2, ni e-mail ni nom). Code de secours affiché une seule fois à l'inscription, seul moyen de changer un mot de passe oublié.
- **Stockage** : SQLite au départ (volume persistant), comptes et conversations. C'est la base dont ont besoin le journal (#18) et les avis (#19).
- **Avancement** : (1) graphe de conversation avec condensation des relances, **fait et fusionné** (PR #25, mesuré : pas de régression, 15 tours sur 18 corrects) ; (2) application Chainlit + comptes + pages d'inscription, de récupération et de suppression, **faite et fusionnée** (PR #28, qui reprend #26 et #27) ; (3) thème Ynov (fond, accent vert/crème, logos clair et sombre, image de connexion, nom « Chatbot Ynov (non officiel) »), **fait et fusionné** (PR #28) ; (4) déploiement Coolify, **fait le 3 octobre** (variable `CHAINLIT_AUTH_SECRET` **créée dans Coolify le 3 octobre**, sauvegarde quotidienne du volume `chat_data` **en place le 4 octobre**).
- **Vu en prototype, non reproduit dans l'application réelle** : une déconnexion en cliquant sur une conversation de la barre latérale. Les liens d'inscription et de récupération sont ajoutés sous le formulaire de connexion par `chat/public/login-links.js`.
- **Pièges de Chainlit 2.12.0** : `requests` et `greenlet` non déclarés (ajoutés à `pyproject.toml`), schéma SQL qui change entre versions (figer la version), chemins des fichiers de `public/` à préfixer par le point de montage.
- **Constats** : salutations et remerciements refusés (EC-16, **inscrit au chantier #14**) ; `POST /api/query` répond désormais 503 (et non 500) quand le LLM est indisponible, après trois tentatives sur 429 et 5xx (PR #38) ; une question qui échoue laisse une conversation vide dans l'historique du chat ; **les messages du chat n'ont aucune limite de fréquence** (la limite de 30 par minute ne vaut que pour `/api/query`), alors que chaque message appelle le LLM ; budget de la clé à surveiller ; `INGEST_API_KEY` a été remplacée le 4 octobre (elle valait `changeme`).

## Ordre suggéré

1. ~~**#15 Intégration continue**~~ : **fait**. `main` est protégée : une PR et trois vérifications (`quality`, `tests`, `retrieval`) sont obligatoires.
2. **#14 Qualité des réponses** et **#21 Rafraîchissement du corpus** : peuvent avancer en parallèle, et se mesurent sur la préprod avant la prod. #21 apporte les versions du corpus, utiles pour comparer les résultats dans le temps.
3. **#18 Journal des réponses** : la base de #19, #20 et des indicateurs d'usage de #16.
4. **#17 Interface utilisateur** (en prod ; reste la limite de fréquence du chat et l'essai par un vrai compte), puis **#19 Bouton d'avis**.
5. **#20 Rapport des questions sans réponse** et **#16 Tableau de bord**, quand le journal contient assez de données.

## Comment avancer sur un chantier

- Une branche par sujet, jamais de commit sur `main` (la branche est protégée) : `feat/…`, `fix/…`, `chore/…`.
- Dans la description de la PR, écrire `Closes #N` : l'issue se ferme automatiquement au merge.
- La CI (`quality`, `tests`, `retrieval`) doit passer avant le merge ; elle n'appelle jamais le LLM. Lancer les mêmes commandes en local avant de pousser.
- Pour tout changement qui touche la recherche ou les réponses : mesurer avant et après avec `eval/retrieval.py` et `eval/e2e.py`, enregistrer les passages et mettre à jour les cas limites concernés. Si une question de référence change de statut volontairement, réécrire la référence de la CI (`eval.retrieval --data eval/ci_corpus --write-baseline eval/ci_baseline.json`).
- Mise en production : déployer la préprod, lancer `gh workflow run production.yml -f label="…"` (26 questions), relire les verdicts, puis déployer la prod.

## Intégration continue et préprod (#15) : décisions du 4 octobre 2026

- **Aucun appel au LLM sur les PR** : `ruff`, `ruff format`, `mypy`, `pytest` (LLM simulé) et `eval.retrieval` sur un petit corpus figé (`eval/ci_corpus/`, 24 sources, 3,7 Mo). La clé Mammouth n'est jamais donnée à GitHub ; l'URL du LLM y pointe vers un port fermé.
- **Préprod** : copie complète de la prod sur le même serveur (application Coolify, base Qdrant, base de chat, corpus et clé Mammouth séparés), derrière un mot de passe géré par l'application (`SITE_PASSWORD`). Le workflow manuel `production.yml` lui pose les 26 questions avant le déploiement de la prod, la clé du LLM restant côté serveur.
- **Protection de `main`** : PR obligatoire, `quality`, `tests` et `retrieval` obligatoires, pas de contournement, pas de suppression ni de réécriture de l'historique.
- **Modèle du LLM** : comparaison de six modèles sur la préprod (qwen3.5-9b trop lent, deepseek-v4-flash instable, quatre autres à 21/26) ; `mammouth-recommended` retenu pour son coût, sa vitesse et l'absence de réponse fausse. C'est un alias : si les réponses changent sans modification du code, regarder d'abord le modèle derrière.
- Détail et pièges dans `documentation/integration-continue.md` et `documentation/preprod.md` (notes locales).
