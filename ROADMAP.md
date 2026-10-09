# Roadmap

Plan du projet RAG Ynov. Chaque chantier est suivi dans une issue GitHub (label `roadmap`), qui contient le détail des tâches, les critères de fin et les dépendances. Ce fichier donne la vue d'ensemble ; l'avancement se lit dans les issues.

## Où en est le projet (6 octobre 2026)

- **Corpus** : 42 formations ynov.com, 7 pages d'information, un document des règles communes et 29 fiches RNCP actives, soit 6 466 chunks (1 447 sections), index hybride dense (MiniLM) + BM25 dans la collection `ynov_rag_v2`.
- **Qualité en prod** : **22 réponses correctes sur 22** questions Ynov (16 de référence + 6 de contrôle), aucune réponse fausse, 10 questions hors sujet sur 10 écartées (`eval/results/2026-10-06_07_preprod-lot7.json`, préprod au même code et au même index que la prod, verdicts relus). C'était 11/16 le 4 octobre (chantier #14).
- **LLM** : `mammouth-recommended` en prod et en préprod depuis le 4 octobre 2026 (environ 0,5 $ pour 1 000 questions ; le contexte plus long du chantier #14 le porte à environ 0,8 $), alias de Mammouth dont le modèle sous-jacent peut changer.
- **Intégration continue** : en place (#15) ; une préprod protégée par mot de passe, évaluée avant chaque mise en production.
- **Suivi** : chaque test est enregistré dans `eval/results/`, chaque anomalie documentée dans `eval/edge_cases.yaml` ; synthèse dans `eval/REPORT.md`.

## Chantiers

| # | Chantier | Domaine | Dépend de |
|---|---|---|---|
| [#14](https://github.com/Romain-Data/RAG-ynov/issues/14) | ~~Améliorer la qualité des réponses~~ **fait le 6 octobre 2026** (de 11/16 à 22/22 questions Ynov, 0 fausse, salutations et remerciements, liens vers les sources ; MiniLM conservé) | qualité | — |
| [#15](https://github.com/Romain-Data/RAG-ynov/issues/15) | ~~Mettre en place l'intégration continue~~ **fait le 4 octobre 2026** (aucun appel au LLM sur les PR ; évaluation sur la préprod avant la mise en production) | infra | — |
| [#16](https://github.com/Romain-Data/RAG-ynov/issues/16) | Tableau de bord de l'évolution des résultats | produit | #18, #19 (pour les indicateurs d'usage) |
| [#17](https://github.com/Romain-Data/RAG-ynov/issues/17) | ~~Interface utilisateur de chat (Chainlit, comptes, historique)~~ **clos** (en prod depuis le 3 octobre 2026, chat sur `/` depuis le 6) ; non traités à la clôture : limite de fréquence du chat, essai par un vrai compte, accessibilité | produit | ~~#14 (liens vers les sources)~~ fait |
| [#18](https://github.com/Romain-Data/RAG-ynov/issues/18) | Journal des réponses pour la revue manuelle : **code fait le 9 octobre 2026** (PR enregistrement + PR interface `/admin`), reste la mise en service (voir ci-dessous) | produit | — |
| [#19](https://github.com/Romain-Data/RAG-ynov/issues/19) | Bouton « réponse satisfaisante ou non » ; inclut aussi : déplacer le bouton de suppression de compte, de la conversation au menu en haut à droite (si possible, sinon en bas de la colonne de gauche) | produit | #17, #18 |
| [#20](https://github.com/Romain-Data/RAG-ynov/issues/20) | Rapport des questions sans réponse | produit | #18 |
| [#21](https://github.com/Romain-Data/RAG-ynov/issues/21) | Rafraîchissement automatique du corpus et suivi des versions | données | — |

## Interface de chat (#17) : décisions du 3 octobre 2026

- **Adresses (6 octobre 2026, PR #52)** : le chat est sur `/` et l'API sous `/api` (infos sur `/api`, Swagger sur `/api/docs`). L'ancien `/chat/` n'est plus l'adresse du chat.

- **Technologie : [Chainlit](https://docs.chainlit.io)**, monté dans l'API FastAPI actuelle. Agent Chat UI a été écarté : il impose un serveur LangGraph (Aegra), PostgreSQL et un front Next.js, soit trois services de plus. Un prototype Chainlit a validé la connexion, l'historique, la reprise d'une conversation et le cloisonnement entre comptes.
- **Connexion obligatoire, pseudo + mot de passe uniquement** (hachage argon2, ni e-mail ni nom). Code de secours affiché une seule fois à l'inscription, seul moyen de changer un mot de passe oublié.
- **Stockage** : SQLite au départ (volume persistant), comptes et conversations. C'est la base dont ont besoin le journal (#18) et les avis (#19).
- **Avancement** : (1) graphe de conversation avec condensation des relances, **fait et fusionné** (PR #25, mesuré : pas de régression, 15 tours sur 18 corrects) ; (2) application Chainlit + comptes + pages d'inscription, de récupération et de suppression, **faite et fusionnée** (PR #28, qui reprend #26 et #27) ; (3) thème Ynov (fond, accent vert/crème, logos clair et sombre, image de connexion, nom « Chatbot Ynov (non officiel) »), **fait et fusionné** (PR #28) ; (4) déploiement Coolify, **fait le 3 octobre** (variable `CHAINLIT_AUTH_SECRET` **créée dans Coolify le 3 octobre**, sauvegarde quotidienne du volume `chat_data` **en place le 4 octobre**).
- **Vu en prototype, non reproduit dans l'application réelle** : une déconnexion en cliquant sur une conversation de la barre latérale. Les liens d'inscription et de récupération sont ajoutés sous le formulaire de connexion par `chat/public/login-links.js`.
- **Pièges de Chainlit 2.12.0** : `requests` et `greenlet` non déclarés (ajoutés à `pyproject.toml`), schéma SQL qui change entre versions (figer la version), chemins des fichiers de `public/` à préfixer par le point de montage (plus de préfixe depuis le 6 octobre 2026 : le chat est monté sur `/`).
- **Constats** : salutations et remerciements refusés (EC-16, **inscrit au chantier #14**) ; `POST /api/query` répond désormais 503 (et non 500) quand le LLM est indisponible, après trois tentatives sur 429 et 5xx (PR #38) ; une question qui échoue laisse une conversation vide dans l'historique du chat ; **les messages du chat n'ont aucune limite de fréquence** (la limite de 30 par minute ne vaut que pour `/api/query`), alors que chaque message appelle le LLM ; budget de la clé à surveiller ; `INGEST_API_KEY` a été remplacée le 4 octobre (elle valait `changeme`).

## Ordre suggéré

1. ~~**#15 Intégration continue**~~ : **fait**. `main` est protégée : une PR et trois vérifications (`quality`, `tests`, `retrieval`) sont obligatoires.
2. ~~**#14 Qualité des réponses**~~ : **fait** ; **#21 Rafraîchissement du corpus** se mesure sur la préprod avant la prod. #21 apporte les versions du corpus, utiles pour comparer les résultats dans le temps ; la commande `python -m ingestion.run` (#14) en est la première brique.
3. **#18 Journal des réponses** : la base de #19, #20 et des indicateurs d'usage de #16. Code fait ; mise en service : `ADMIN_PASSWORD` dans Coolify (préprod puis prod), tâche planifiée `python -m journal.purge` chaque jour, essai de 2 ou 3 questions sur la préprod.
4. ~~**#17 Interface utilisateur**~~ : **clos** (en prod) ; puis **#19 Bouton d'avis**, avec le déplacement du bouton de suppression de compte.
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

## Qualité des réponses (#14) : décisions du 6 octobre 2026

- **Le goulot n'était pas le LLM** : les 5 échecs de bout en bout du 4 octobre étaient exactement les questions dont les faits attendus manquaient dans le contexte envoyé au LLM. `eval.retrieval` mesure maintenant ces « faits dans le contexte » (jeu de questions v11, 22 questions Ynov dont 6 de contrôle), ce que le critère « bonne section récupérée » ne voyait pas (EC-18).
- **Six changements, une PR chacun** : section entière envoyée au LLM quand elle fait 2 000 caractères au plus (#43), une section par module de programme et une synthèse des blocs RNCP, seuil 0,45 → 0,47 (#44), recherche hybride dense + BM25 par injection de 2 résultats et commande `python -m ingestion.run` (#45), salutations et remerciements sans recherche ni LLM (#46), règle 4 du prompt « en entier » (#47), liens vers les sources (#48).
- **Modèle d'embedding : MiniLM conservé.** L'objectif est atteint sans e5-large (2,2 Go de RAM, 38 minutes d'ingestion, seuil fragile). Reranker et filtres déduits de la question : reportés, sans objet tant que l'objectif tient.
- **Liste des campus (9 octobre 2026, PR #55 et #56)** : « Où sont les campus ? » ne trouvait pas de liste (elle n'était que sur `/campus`, non récupérée, et dans les « Lieux » de chaque formation). `/campus` rejoint les pages communes et `ingestion.build_common` en tire une section « Liste des campus Ynov » ; q33 et q34 (jeu v13) ; 34/34 en préprod. Les pages `/campus/<ville>` ont été écartées (la météo à Lyon passait le seuil). Un premier essai tenait seulement avec « d'Ynov » : tester plusieurs formulations. À prévoir : un script qui ingère dans une nouvelle collection, vérifie qu'elle existe et que le nombre de chunks est cohérent, puis bascule (l'ingestion fait ~2,7 Go de RAM : swap de 4 Go posé sur le serveur).
- **Mise en production** : réingestion dans une nouvelle collection (`ynov_rag_v2`, `python -m ingestion.run --collection`) pendant que l'API servait l'ancienne, puis bascule de `QDRANT_COLLECTION_NAME` et redémarrage, sans coupure. L'ancienne collection `ynov_rag` est conservée pour un retour arrière et à supprimer après quelques jours.
- **Limites restantes** : seuil à marges étroites (0,008 côté hors sujet, 0,022 côté légitime), à recalibrer si le corpus ou le découpage changent ; le LLM recopie parfois l'en-tête du chunk au début de sa réponse ; le lien d'une source renvoie à la page, pas à la section ; le document des règles communes n'a pas d'URL.

## Journal des réponses (#18) : décisions du 9 octobre 2026

- **Stockage** : table `answer_log` dans la base SQLite du chat (déjà sauvegardée chaque jour), pas de Postgres ni de fichiers : le volume est faible et les avis de #19 se joindront par `thread_id`/`message_id`. Une entrée par question, chat et `POST /api/query` (canal `api`), erreurs du LLM comprises ; le journal n'empêche jamais une réponse.
- **Contenu** : question (e-mails et téléphones masqués), reformulation, réponse, issue (`generate`, `refuse`, `smalltalk`, `error`), meilleur score, sources, 10 résultats sans leur texte, modèle réel renvoyé par Mammouth et alias, jetons, latence, collection, modèle d'embedding, seuil, commit déployé.
- **RGPD** : ni pseudo ni IP ; suppression d'un compte = les entrées restent mais perdent leur lien avec la conversation ; conservation 180 jours (`ANSWER_LOG_RETENTION_DAYS`, `python -m journal.purge`) ; `ANSWER_LOG_ENABLED=false` coupe l'écriture ; phrase d'information sur la page d'inscription.
- **Interface `/admin`** : formulaire de connexion (pas de HTTP Basic, la préprod en a déjà un), mot de passe `ADMIN_PASSWORD` (sans lui, `/admin` n'est pas monté), cookie signé de 8 h, limite de tentatives, contrôle de l'en-tête `Origin` sur les POST, CSP sans script, tout contenu échappé. Liste filtrable, fiche de revue (bonne, partielle, fausse, hors sujet), extrait YAML à coller dans `eval/questions.yaml`.
