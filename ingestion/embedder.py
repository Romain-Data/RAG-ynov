"""Local embeddings with FastEmbed (ONNX)."""

from fastembed import TextEmbedding

from app.core.config import settings

# Global model instance (lazy)
_embedding_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    """Get or create the FastEmbed model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(
            model_name=settings.embedding_model,
            cache_dir=(
                settings.fast_embed_cache_dir
                if hasattr(settings, "fast_embed_cache_dir")
                else None
            ),
        )
    return _embedding_model  # type: ignore[return-value]


def embed_passages(texts: list[str]) -> list[list[float]]:
    """
    Embed document chunks (passages).
    Note: paraphrase-multilingual-MiniLM-L12-v2 does not require e5 prefixes.
    """
    model = get_embedding_model()
    # Type: ignore because FastEmbed returns numpy arrays but they are convertible
    return [list(vec) for vec in model.embed(texts)]  # type: ignore[arg-type]


def embed_query(text: str) -> list[float]:
    """
    Embed a user query.
    Note: paraphrase-multilingual-MiniLM-L12-v2 does not require e5 prefixes.
    """
    model = get_embedding_model()
    result = list(model.embed([text]))[0]  # type: ignore[index]
    return list(result)  # type: ignore[arg-type]