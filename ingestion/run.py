"""Ingest data/ into Qdrant: load, chunk, embed (dense + BM25) and index.

Replaces the script pasted in the Coolify terminal, and is what /api/ingest runs. Embedding
takes a few minutes with MiniLM on the server (about 40 minutes with e5-large).

Usage:
    uv run python -m ingestion.run [--data data]
"""

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from app.core.config import settings
from ingestion.chunking import chunk_documents
from ingestion.embedder import embed_passages, embed_sparse_passages
from ingestion.indexer import index_chunks
from ingestion.loaders import load_directory

BATCH = 256


def ingest_directory(data_dir: Path, log: Callable[[str], None] = lambda _msg: None) -> int:
    """Index every document of `data_dir`; returns the number of points, 0 for no document."""
    start = time.time()
    docs = load_directory(data_dir, settings.ingest_exclude_doc_type_list())
    if not docs:
        return 0
    chunks = chunk_documents(docs)
    log(f"{len(docs)} sections, {len(chunks)} chunks")
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        texts = [c["text"] for c in batch]
        for chunk, dense, sparse in zip(
            batch, embed_passages(texts), embed_sparse_passages(texts), strict=True
        ):
            chunk["vector"] = dense
            chunk["sparse"] = sparse
        log(f"embeddings {min(i + BATCH, len(chunks))}/{len(chunks)} ({time.time() - start:.0f}s)")
    count = index_chunks(chunks)
    log(f"{count} points indexés en {time.time() - start:.0f}s")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    args = parser.parse_args()
    ingest_directory(args.data, lambda msg: print(msg, flush=True))


if __name__ == "__main__":
    main()
