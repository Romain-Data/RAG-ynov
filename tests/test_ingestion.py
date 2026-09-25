"""End-to-end test of the ingestion pipeline on the sample Markdown."""
import asyncio
from pathlib import Path

from ingestion.chunking import chunk_documents
from ingestion.embedder import embed_passages
from ingestion.indexer import index_chunks
from ingestion.loaders import load_directory


async def main():
    data_dir = Path("data/samples")

    # 1. Load
    print("Loading documents...")
    docs = load_directory(data_dir)
    print(f"  Loaded {len(docs)} document(s)")

    # 2. Chunk
    print("Chunking...")
    chunks = chunk_documents(docs, chunk_size=500, chunk_overlap=50)
    print(f"  Created {len(chunks)} chunks")

    # 3. Embed
    print("Embedding...")
    texts = [c["text"] for c in chunks]
    vectors = embed_passages(texts)
    print(f"  Embedded {len(vectors)} vectors (dim={len(vectors[0])})")

    # Attach vectors to chunks
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk["vector"] = vector

    # 4. Index
    print("Indexing to Qdrant...")
    count = index_chunks(chunks)
    print(f"  Indexed {count} points")

    print("\n✅ Ingestion pipeline test passed!")


if __name__ == "__main__":
    asyncio.run(main())
