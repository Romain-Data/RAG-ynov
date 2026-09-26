"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (Mammouth)
    mammouth_api_key: str
    mammouth_base_url: str = "https://api.mammouth.ai/v1"
    mammouth_chat_model: str = "mistral-medium-2407"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "ynov_rag"

    # Embedding (local FastEmbed)
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    fast_embed_cache_dir: str = "/app/.fastembed_cache"

    # Ingest (CLI-only in V1 — header X-Ingest-Key)
    ingest_api_key: str = "changeme"

    # CORS — comma-separated origins, or "*" for all (dev only)
    cors_origins: str = "*"

    # Rate limiting (requests per minute per IP)
    rate_limit_query: int = 30
    rate_limit_ingest: int = 5
    rate_limit_health: int = 120

    # Misc
    log_level: str = "INFO"

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw in {"*", '["*"]'}:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
