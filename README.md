# RAG Ynov

Retrieval-augmented generation system for Ynov school documents (programs and admissions). Built as a portfolio project demonstrating RAG architecture with local embeddings and external LLM.

## Stack

- Python 3.12+
- FastAPI — REST API
- LangGraph — RAG pipeline orchestration (retrieval + generation)
- Qdrant — Vector database (Docker)
- FastEmbed — Local embeddings (ONNX, intfloat/multilingual-e5-small)
- Mammouth AI — LLM for generation (external API)
- uv — Dependency management
- Docker Compose — Deployment (Coolify/Traefik ready)

## Architecture

```
User Question
        │
        ▼
Retrieve (Qdrant KNN search)
        │
        ▼
Grade (similarity score threshold)
        │
        ▼
Generate (Mammouth AI)        Refuse if score < threshold
        │                       │
        ▼                       ▼
Answer + Sources          Polite refusal message
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
questions ("Et à Lyon ?") through the conversation graph (`graph/chat.py`).

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

## Roadmap

The project plan lives in [ROADMAP.md](ROADMAP.md), each item tracked in a GitHub issue labelled `roadmap`.

## Project Structure

```
rag-ynov/
├── app/                    # FastAPI application
│   ├── api/                # Routes (/health, /query, /ingest)
│   ├── core/               # Configuration, logging
│   └── schemas/            # Pydantic models
├── ingestion/              # Ingestion pipeline (load → chunk → embed → index)
├── graph/                  # LangGraph nodes + builder
│   └── nodes/              # retrieve, grade, generate, refuse
├── data/                   # Corpus, not in git: python -m ingestion.fetch, copied to the server
├── tests/                  # fixtures/: a fictitious FAQ for loader tests only
├── docker/
│   └── api.Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Git Branches

| Branch              | Content                                                          |
|---------------------|------------------------------------------------------------------|
| chore/init-project  | Initial setup: uv, Docker, configuration, logging                |
| feat/ingestion      | Ingestion pipeline: loaders, chunking, embedder, Qdrant indexer  |
| feat/graph          | LangGraph: StateGraph, nodes (retrieve, grade, generate, refuse) |
| feat/api            | REST endpoints: /health, /query, /ingest with error handling     |
| feat/docker         | Dockerfile, docker-compose Coolify-ready, final README           |

## Coolify Deployment

The `docker-compose.yml` is compatible with Coolify:

- API container exposes port 8000 internally (Traefik handles external routing)
- Qdrant uses persistent volume `qdrant_storage`
- Healthcheck configured on Qdrant `/healthz` endpoint
- Environment variables loaded from `.env` (never committed)
- No port conflicts with other services on the VPS

## Testing

```bash
# Run test suite
uv run pytest

# Run with coverage (if configured)
uv run pytest --cov=app --cov=ingestion --cov=graph
```

## License

MIT — Educational portfolio project.