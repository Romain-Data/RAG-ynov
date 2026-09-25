from app.core.config import settings
from graph.state import GraphState
from ingestion.embedder import embed_query
from ingestion.indexer import get_qdrant_client


def retrieve_node(state: GraphState) -> dict:
    """Embed question and search Qdrant for relevant chunks."""
    question = state.get("question", "")
    if not question:
        return {"retrieved": []}

    query_vector = embed_query(question)
    client = get_qdrant_client()

    response = client.query_points(
        collection_name=settings.qdrant_collection_name,
        query=query_vector,
        limit=5,
        with_payload=True,
    )

    retrieved = []
    for point in response.points:
        payload = point.payload or {}
        retrieved.append({
            "text": payload.get("text", ""),
            "score": point.score,
            "source": payload.get("source", ""),
            "page": payload.get("page"),
            "section": payload.get("section"),
            "metadata": payload,
        })

    return {"retrieved": retrieved}
