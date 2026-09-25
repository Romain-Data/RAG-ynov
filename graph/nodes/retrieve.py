from graph.state import GraphState


def retrieve_node(state: GraphState) -> GraphState:
    """Embed question and search Qdrant for relevant chunks."""
    # TODO: Implement with FastEmbed + Qdrant client
    # 1. Embed the question (with "query: " prefix for e5)
    # 2. Search Qdrant collection with k=5
    # 3. Return chunks with scores and metadata
    return {"retrieved": []}