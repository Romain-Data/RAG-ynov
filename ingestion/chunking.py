"""Text chunking strategies."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

# The embedding model (paraphrase-multilingual-MiniLM-L12-v2) truncates its input at
# 128 tokens: anything beyond is invisible to retrieval. ~300 characters of French plus
# the context prefix fit in that budget (500 left half of the chunks truncated).
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
# A section up to this size is stored whole in the payload of each of its chunks
# (`section_text`): retrieval finds the chunk, generation reads the section (EC-17).
SECTION_CONTEXT_MAX = 2000


def chunk_documents(
    documents: list[dict],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split documents into chunks.

    Args:
        documents: List of {text, metadata} from loaders, with an optional `prefix`
            prepended to every chunk (e.g. "<formation> — <section>" for HTML pages)
        chunk_size: Target chunk size in characters (approximate)
        chunk_overlap: Overlap between chunks

    Returns:
        List of {text, metadata} with chunked text
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = []
    for doc in documents:
        prefix = doc.get("prefix", "")
        texts = splitter.split_text(doc["text"])
        whole = prefix + doc["text"]
        keep_whole = len(texts) > 1 and len(whole) <= SECTION_CONTEXT_MAX
        for i, text in enumerate(texts):
            if text.strip():
                metadata = doc["metadata"].copy()
                metadata["chunk_index"] = i
                if keep_whole:
                    metadata["section_text"] = whole
                chunks.append({"text": prefix + text, "metadata": metadata})

    return chunks
