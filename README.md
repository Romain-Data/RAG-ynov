# RAG Ynov

RAG pédagogique sur les programmes Ynov et admissions — Portfolio project.

## Stack

- **Python** 3.12+
- **FastAPI** — API REST
- **LangGraph** — Orchestration du pipeline RAG (retrieval + generation)
- **Qdrant** — Base vectorielle (Docker)
- **FastEmbed** — Embeddings locaux (ONNX, `intfloat/multilingual-e5-small`)
- **Mammouth AI** — LLM pour la génération (API externe)
- **uv** — Gestion des dépendances
- **Docker Compose** — Déploiement (Coolify/Traefik ready)

## Architecture

```
Question → Retrieve (Qdrant KNN) → Grade (seuil score) → Generate (Mammouth) → Réponse + sources
                            ↓
                      Refuse si score < seuil
```

## Démarrage rapide

```bash
# 1. Copier l'exemple d'environnement
cp .env.example .env
# Éditer .env avec votre clé Mammouth

# 2. Lancer l'infra (Qdrant + API)
docker compose up -d

# 3. Vérifier la santé
curl http://localhost:8000/api/health

# 4. Ingérer des documents (quand implémenté)
curl -X POST http://localhost:8000/api/ingest

# 5. Poser une question
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Comment s\'inscrire avec un bac pro ?"}'
```

## Structure du projet

```
rag-ynov/
├── app/                    # FastAPI application
│   ├── api/                # Routes (/health, /query, /ingest)
│   ├── core/               # Config, logging
│   └── schemas/            # Pydantic models
├── ingestion/              # Pipeline d'ingestion (load → chunk → embed → index)
├── graph/                  # LangGraph nodes + builder
│   └── nodes/              # retrieve, grade, generate, refuse
├── data/
│   └── samples/            # Corpus d'exemple (git-ignored en prod)
├── tests/
├── docker/
│   └── api.Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Branches Git

| Branche | Contenu |
|---------|---------|
| `chore/init-project` | Setup infra, uv, docker, config |
| `feat/ingestion` | Pipeline load → chunk → embed → index |
| `feat/graph` | LangGraph retrieve → grade → generate/refuse |
| `feat/api` | Endpoints /query, /ingest fonctionnels |
| `feat/docker` | Dockerfile, compose Coolify-ready, README final |

## Déploiement Coolify

Le `docker-compose.yml` est compatible Coolify :

- API sur port interne 8000 (routé par Traefik)
- Qdrant avec volume persistant `qdrant_storage`
- Healthcheck sur `/healthz` Qdrant
- Variables via `.env` (jamais committé)
- Pas de conflit de ports avec d'autres projets sur le VPS

## Licence

MIT — Projet pédagogique portfolio.