# RAG Ynov

Retrieval-augmented generation system for Ynov school documents (programs and admissions). Built as a portfolio project demonstrating RAG architecture with local embeddings and external LLM.

## Stack

- Python 3.12+
- FastAPI — REST API
- LangGraph — RAG pipeline orchestration (retrieval + generation)
- Qdrant — Vector database (Docker), hybrid search: dense vectors + BM25 sparse vectors
- FastEmbed — Local embeddings (ONNX, sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) and BM25
- Mammouth AI — LLM for generation (external API, `mammouth-recommended` in production)
- Chainlit — Chat interface, mounted on the API
- SQLite — Accounts, conversations, answer journal and user feedback
- uv — Dependency management
- Docker Compose — Deployment (Coolify/Traefik ready)

## Architecture

```
User question
        │
        ▼
Smalltalk? (greetings, thanks) ── yes ──▶ fixed reply, no search, no LLM
        │ no
        ▼
Condense (chat only: a follow-up becomes a standalone question)
        │
        ▼
Retrieve (Qdrant: dense MiniLM + BM25)
        │
        ▼
Grade (cosine score threshold)
        │
        ▼
Generate (Mammouth AI)        Refuse if score < threshold
        │                       │
        ▼                       ▼
Answer + Sources          Polite refusal message
        │
        ▼
Answer journal (SQLite) ◀── users' thumbs in the chat, reviewed on /admin
```

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env with your Mammouth API key

# 2. Start infrastructure (Qdrant + API)
docker compose up -d

# 3. Verify health endpoint (also tells the models, collection, threshold and deployed commit)
curl http://localhost:8000/api/health

# 4. Ingest documents (dense + BM25 index). Same as: python -m ingestion.run [--collection NAME]
curl -X POST http://localhost:8000/api/ingest \
  -H "X-Ingest-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{}'

# 5. Ask a question
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels sont les frais de scolarité ?"}'
```

## Chat interface

A chat for the public, served by the same API on `/` ([Chainlit](https://chainlit.io)).
Users create an account with a **pseudo and a password, nothing else** (no e-mail, no
name): the sign-up page shows a one-time recovery code, the only way to reset a forgotten
password. Conversations keep their history, can be reopened later and answer follow-up
questions ("Et à Lyon ?") through the conversation graph (`graph/chat.py`). Under each answer,
thumbs ("Utile" / "Pas utile", with an optional comment) tell whether it helped: see
[Answer journal and review](#answer-journal-and-review).

```bash
# Generate the secret signing the session cookies, put it in .env, then start the stack
uv run chainlit create-secret          # -> CHAINLIT_AUTH_SECRET=...
docker compose up -d --build
# Chat:           http://localhost:8000/
# Create account: http://localhost:8000/compte/inscription
```

Without `CHAINLIT_AUTH_SECRET` the chat is not mounted and the API works as before.
Accounts and conversations live in one SQLite file (`CHAT_DB_PATH`, the `chat_data`
volume): back it up. `python -m chat.backup` copies it (SQLite backup API, integrity check,
14 copies kept); in production a daily task in Coolify runs it and the copies land on the host in
`/data/rag-ynov-backups`, outside the Docker volume. Pages: `/compte/inscription`, `/compte/recuperation`,
`/compte/suppression` (deletes the account and its conversations).

Chainlit has no hook for these pages, so `chat/public/custom.js` (its single `custom_js`) adds
the sign-up and recovery links under the login form, and a "Supprimer mon compte" entry to the user
menu (the round button with the initial of the pseudo, top right), just above "Se déconnecter".
The greeting is not part of the conversation history: when a conversation is reopened, the assistant
messages before the first question are left out, whatever their text.

## Answer journal and review

Every question asked in the chat or on `POST /api/query` is written to the `answer_log` table
of the chat database (`journal/`): the answer, its sources, the search scores, the model that
really answered (the `model` field of the LLM response, since `MAMMOUTH_CHAT_MODEL` is an alias),
the collection and the threshold (on 12 October 2026 the `model` field of `mammouth-recommended`
only repeated the alias, so a change of model behind it may not show). No pseudo and no IP are kept, e-mail addresses and phone numbers
are masked, and entries older than `ANSWER_LOG_RETENTION_DAYS` (180) are deleted by
`python -m journal.purge`, a daily task in Coolify. `ANSWER_LOG_ENABLED=false` stops the writing.
The journal never blocks an answer.

The thumbs that Chainlit shows under each answer of the chat ("Utile" / "Pas utile", with an
optional comment) are copied to the entry of that answer (`feedback` 1 or 0, `feedback_comment`,
masked like the question, and `feedback_at`) by a subclass of Chainlit's data layer
(`chat/feedback.py`). `PUT` and `DELETE /feedback` go through a guard declared before Chainlit: the
answer must belong to a conversation of the signed-in user, one feedback per answer, a comment of
1,000 characters at most, `RATE_LIMIT_FEEDBACK` (30) requests per minute per IP. A feedback stays in
the journal when its account is deleted (without the tie to the conversation) and goes with its
entry after 180 days. `POST /api/query` has no feedback.

`/admin` (set `ADMIN_PASSWORD`, otherwise it is not mounted) lists the entries, shows the detail of
each one and lets the reviewer classify it (bonne, partielle, fausse, hors_sujet), then gives an
excerpt to paste into `eval/questions.yaml`. The users' thumbs show there too: an "Avis" column and
filter in the list (Utile, Pas utile, without feedback), a shortcut to the "Pas utile" answers not
reviewed yet, and the feedback, its comment and its date on the detail page. `/admin/synthese` sums
the journal up (how answers end crossed with the reviews, the users' feedback per route with the
satisfaction rate next to the number of votes, a total without the replies to greetings, feedback
crossed with the reviews, search scores per review next to the threshold, models that answered, days,
errors) over all of it or the last 7 or 30 days. Login is a form with a signed 8-hour cookie, not HTTP
Basic (the preprod already has one in front of the whole site).

The questions left without an answer (#20, `journal/gaps.py`) are worked out when the journal is
read, never stored, so that a better rule applies to the older entries too. Each entry gets at
most one kind: a refusal at the threshold (`refus`), a refusal of the LLM for a question outside
Ynov (`hors_ynov`, rule 5 of the prompt), an LLM that says it cannot answer from the context
(`aveu`: "Je ne peux pas répondre…", or nothing but "Le contexte ne précise pas…"), an answer
that also says part of it is missing (`incomplete`), or any other answer rated "Pas utile"
(`pas_utile`); greetings and errors have none. The wordings come from the answers saved in
`eval/results/` (`tests/fixtures/gap_answers.yaml`, labelled by hand). `gap_kind` is also an SQL
function on every connection to the chat database: the list of `/admin` has a "Sans réponse"
filter (any kind, no answer at all, or one kind), the kind shows in the list and on the detail
page, and `/admin/synthese` counts each kind out of the questions that went to the search.

These questions are then grouped by theme by the LLM (`journal/themes.py`), on demand: a button of
`/admin/sans-reponse` (or `python -m journal.themes`) sends at most 100 distinct questions per call,
with the existing themes so that the LLM reuses them, two of them fixed ("Autres écoles", "Hors
sujet"). The model that compares a question to a passage in the search cannot group two short
questions worded differently, hence the LLM. Nothing is written when the call fails; an answer cut
by `max_tokens` is asked again for half the batch. The theme is stored (`gap_theme` table,
`answer_log.gap_theme_id`) so that it stays the same from one report to the next. Each theme page
shows its questions, their kinds and conversations, a suggested cause and what the search finds
today for its example question (no LLM), and records the cause decided by hand: nothing on the
site (`contenu`), not a question about Ynov (`hors_sujet`), or a page the search missed
(`recherche`), with a note. Themes can be renamed and merged, questions moved. The prompt was
calibrated on 40 fictive questions (`tests/fixtures/gap_questions.yaml`); the two recorded answers
of the LLM are replayed by the tests.

Each month gets a report (`/admin/rapport?mois=AAAA-MM`, `journal/report.py`) written for someone
who is not technical: the questions of the month next to the month before, the themes the site
does not cover (cause `contenu`, then the themes not decided yet), the ones the chatbot should have
answered (`recherche`, with the note of the theme), the off-topic ones, and how to read it. Per
theme: questions, conversations, trend and up to two example questions, quoted only when the theme
came up in at least two conversations of the month (a question asked once may tell who asked it).
`&telecharger=1` returns the same report as a standalone HTML file (styles inside, no link, form
or script, printable to PDF), the archive of a month once its questions are purged;
`python -m journal.report --mois AAAA-MM --out report.html` writes it from a local copy of the
database. Read-only, no LLM call.

`/admin/tableau-de-bord` (#16) shows how the measured quality evolves, from the evaluation runs
of `eval/results/` (they are in the Docker image: a run shows once the pull request that saves it
is deployed). In brief, the last end-to-end run of each environment (with its model, collection
and deployed commit, marked « reconstitué » when filled in afterwards), the last retrieval run
with the margins of the threshold, and the open edge cases; then, over the runs, the share of Ynov
questions answered right, the 16 reference questions q01–q16 (asked since 2 October, the only
score comparable from end to end) and the wrong answers, one line per environment, with numbered
marks where the question set, the model, the collection or the threshold changed; the retrieval
milestones and the extreme scores against the threshold; the question × run matrix (end to end or
retrieval, milestones or all runs, one environment or all, filters in the query string); the edge
cases per status; how often the automatic check agrees with the review. The figures come from the
verdicts as reviewed by hand (`eval/dashboard.py`, shared with `eval/REPORT.md`); the charts are
inline SVG drawn by Python (`admin/charts.py`), each followed by its table, with no script (the CSP
of `/admin` allows none). A run file that cannot be read is listed at the bottom of the page.

The same page ends with the real usage, from the journal week by week (Monday to Sunday, UTC, the
last 12 weeks at most; `journal/stats.py::weekly`, drawn by `admin/usage.py`), with the
definitions of `/admin/synthese`: questions per week (chat and API, greetings apart), the share left
without an answer and the refusals at the threshold, the satisfaction of the chat (share of « Utile »
among the votes, greetings apart), then a table per week that adds the incomplete answers, the
errors, the reviews, the median time of a generated answer and its tokens. A rate always comes with
its count, and a point computed on fewer than 10 questions or votes is drawn hollow; with less than
two weeks of data, the table comes alone. The evaluation runs of the preprod and the production and
the values of the configuration seen for the first time in the journal (model of the LLM,
collection, embedding model, threshold, version: `config_changes`) are numbered marks on the same
weeks, and the configurations are listed with their first and last date. A card of « En bref » sums
up the last four weeks. The version stays empty while Coolify does not give `SOURCE_COMMIT` (its
« Include Source Commit in Build » setting is off). Read-only, no LLM call.

## Roadmap

The project plan lives in [ROADMAP.md](ROADMAP.md), each item tracked in a GitHub issue labelled `roadmap`.

## Project Structure

```
rag-ynov/
├── app/                    # FastAPI application
│   ├── api/                # Routes (/api/health, /api/query, /api/ingest)
│   ├── core/               # Configuration, logging, rate limits
│   └── schemas/            # Pydantic models
├── chat/                   # Chat interface (Chainlit), accounts, feedback guard, SQLite schema, backups
├── journal/                # Journal of the answers: writing, feedback, purge, review queries, summary, questions without an answer, their themes and their monthly report
├── admin/                  # /admin pages: review of the journal, dashboard and its SVG charts
├── eval/                   # Question sets, retrieval and end-to-end evaluation, figures of the dashboard
├── ingestion/              # Ingestion pipeline (fetch → load → chunk → embed → index)
├── graph/                  # LangGraph graphs: builder.py (API), chat.py (conversation)
│   └── nodes/              # smalltalk, condense, retrieve, grade, generate, refuse
├── data/                   # Corpus, not in git: python -m ingestion.fetch, copied to the server
├── tests/                  # fixtures/: a fictitious FAQ for loader tests only
├── docker/
│   └── api.Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Branches and pull requests

`main` is protected: every change goes through a branch named after its subject (`feat/…`,
`fix/…`, `chore/…`, `docs/…`) and a pull request, and the `quality`, `tests` and `retrieval`
checks must pass. The CI never calls the LLM. See "Comment avancer sur un chantier" in
[ROADMAP.md](ROADMAP.md).

## Coolify Deployment

The `docker-compose.yml` is compatible with Coolify:

- API container exposes port 8000 internally (Traefik handles external routing)
- Qdrant uses persistent volume `qdrant_storage_v1_19`, the chat database the `chat_data` volume
- Healthchecks: the API on `/api/health`, Qdrant on its port 6333
- Environment variables loaded from `.env` (never committed)
- No port conflicts with other services on the VPS

A preprod (`docker-compose.preprod.yml`, behind a site password) runs the same code and is
deployed and evaluated before production.

## Testing

```bash
# What the CI runs on every pull request (no LLM call: it is mocked in the tests)
uv run ruff check .
uv run ruff format --check .
uv run mypy app ingestion graph chat eval journal admin
uv run pytest -q
uv run python -m eval.retrieval --data eval/ci_corpus --check eval/ci_baseline.json
```

## Evaluation

Every evaluation run is saved in `eval/results/`, one JSON file per run (format described in
`eval/results.py`), summarised in [eval/REPORT.md](eval/REPORT.md) by
`uv run python -m eval.report` and drawn over time on `/admin/tableau-de-bord` (see above). Both
count from the reviewed verdicts, not from the `summary` saved with the run, which is not updated
when a verdict is corrected by hand.

```bash
uv run python -m eval.retrieval --save "label"    # retrieval only, local index, no LLM call
uv run python -m eval.e2e --local --save "label"  # the graph in process, LLM of the local .env
uv run python -m eval.e2e --url https://rag-preprod.romaincollery.com --environment preprod \
  --save "label"                                  # the questions asked to a server
```

A run on a server (the `production.yml` workflow asks the preprod before each production
deployment) reads `/api/health` before and after the questions and records what answered:
`config.llm_model` (the configured model, `mammouth-recommended` is an alias: Mammouth does not
tell the model behind it), `embedding_model`, `collection`, `grade_threshold`, `server_version`
(the deployed commit, `SOURCE_COMMIT`, empty unless Coolify's "Include Source Commit in Build" is
on) and the whole answer in `config.server`. A change between the two reads (a deployment during
the run) is printed and added to `notes`. The runs on a server saved before 12 October 2026 only
had the URL: their model comes from the documented history, marked
`"llm_model_source": "reconstitué"`. `QUESTION_SET` must be the last version documented at the
top of `eval/questions.yaml` (a test checks it).

## License

MIT — Educational portfolio project.