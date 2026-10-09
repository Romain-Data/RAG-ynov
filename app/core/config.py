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
    # Manifest doc_types left out of ingestion, comma-separated. V1 skips the RNCP
    # référentiel PDFs: their tables extract as interleaved columns, and the RNCP fiches
    # already carry the skill blocs cleanly.
    ingest_exclude_doc_types: str = "referentiel"

    # CORS — comma-separated origins, or "*" for all (dev only)
    cors_origins: str = "*"

    # Chat interface (Chainlit, mounted on /): SQLite file holding the accounts and
    # the conversations, and the secret signing the session cookies. Without the secret
    # the chat is not mounted (Chainlit refuses to start without it).
    chat_db_path: str = "chat_data/chat.db"
    # Where `python -m chat.backup` writes its copies of the chat database, and how many it keeps
    chat_backup_dir: str = "chat_backups"
    chat_backup_keep: int = 14
    chainlit_auth_secret: str = ""

    # Journal of the answers (#18), in the chat database: how long the entries are kept
    # (python -m journal.purge) and a switch to stop writing them.
    answer_log_enabled: bool = True
    answer_log_retention_days: int = 180

    # HTTP Basic password in front of the whole site (user "preprod"), for the preprod.
    # Empty = no protection (production).
    site_password: str = ""

    # Rate limiting (requests per minute per IP)
    rate_limit_query: int = 30
    rate_limit_ingest: int = 5
    rate_limit_health: int = 120
    rate_limit_account: int = 20

    # Misc
    log_level: str = "INFO"

    def ingest_exclude_doc_type_list(self) -> list[str]:
        return [t.strip() for t in self.ingest_exclude_doc_types.split(",") if t.strip()]

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw in {"*", '["*"]'}:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]  # required fields come from the environment
