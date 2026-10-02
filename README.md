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

# 4. Ingest documents (when implemented)
curl -X POST http://localhost:8000/api/ingest \
  -H "X-Ingest-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{}'

# 5. Ask a question
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels sont les frais de scolarité ?"}'
```

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