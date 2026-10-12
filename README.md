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

# 3. Verify health endpoint
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
the collection and the threshold. No pseudo and no IP are kept, e-mail addresses and phone numbers
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
├── journal/                # Journal of the answers: writing, feedback, purge, review queries, summary
├── admin/                  # /admin pages that review the journal
├── eval/                   # Question sets, retrieval and end-to-end evaluation
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

## License

MIT — Educational portfolio project.