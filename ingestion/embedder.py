"""Local embeddings with FastEmbed (ONNX)."""

import os
import shutil
from pathlib import Path

from fastembed import TextEmbedding
from fastembed.common.utils import define_cache_dir

from app.core.config import settings

# Models trained with asymmetric prefixes. paraphrase-multilingual-* models take none.
PREFIXES: dict[str, tuple[str, str]] = {  # model -> (query prefix, passage prefix)
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
}

# One instance per model name (lazy): the model is read from settings at call time, so
# eval/ can compare models in a single process by changing settings.embedding_model.
_models: dict[str, TextEmbedding] = {}


def _snapshot_without_symlinks(name: str, cache_dir: str | None) -> Path | None:
    """Copy of the model's Hugging Face snapshot made of regular files (hard links).

    Large models keep their weights in an external file (model.onnx_data). The Hugging
    Face cache stores it as a symlink to ../../blobs/, and onnxruntime >= 1.2x refuses
    external data that resolves outside the model directory. Hard links share the blob
    without using more disk; a plain copy is the fallback across filesystems.
    """
    description = next((m for m in TextEmbedding.list_supported_models()
                        if m["model"] == name), None)
    repo = (description or {}).get("sources", {}).get("hf")
    if not repo:
        return None
    base: Path = Path(str(define_cache_dir(cache_dir))).expanduser()
    snapshots = sorted((base / f"models--{repo.replace('/', '--')}" / "snapshots").glob("*"))
    if not snapshots:
        return None
    source = snapshots[-1]
    target: Path = base / "materialized" / repo.replace("/", "--") / source.name
    if not target.exists():
        partial = target.with_name(target.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        partial.mkdir(parents=True)
        for file in source.iterdir():
            try:
                os.link(file.resolve(), partial / file.name)
            except OSError:
                shutil.copy2(file.resolve(), partial / file.name)
        partial.rename(target)
    return target


def get_embedding_model() -> TextEmbedding:
    """Get or create the FastEmbed model configured in settings."""
    name = settings.embedding_model
    if name not in _models:
        cache_dir = getattr(settings, "fast_embed_cache_dir", None)
        try:
            _models[name] = TextEmbedding(model_name=name, cache_dir=cache_dir)
        except Exception as exc:  # onnxruntime raises its own Fail type
            if "External data path" not in str(exc):
                raise
            path = _snapshot_without_symlinks(name, cache_dir)
            if path is None:
                raise
            _models[name] = TextEmbedding(model_name=name, cache_dir=cache_dir,
                                          specific_model_path=str(path))
    return _models[name]


def _prefixes() -> tuple[str, str]:
    return PREFIXES.get(settings.embedding_model, ("", ""))


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed document chunks (passages), with the model's passage prefix if any."""
    model = get_embedding_model()
    prefix = _prefixes()[1]
    return [list(vec) for vec in model.embed([prefix + t for t in texts])]


def embed_query(text: str) -> list[float]:
    """Embed a user query, with the model's query prefix if any."""
    model = get_embedding_model()
    result = list(model.embed([_prefixes()[0] + text]))[0]
    return list(result)
