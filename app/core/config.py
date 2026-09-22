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
    embedding_model: str = "intfloat/multilingual-e5-small"
    fast_embed_cache_dir: str = "/app/.fastembed_cache"

    # Misc
    log_level: str = "INFO"


settings = Settings()