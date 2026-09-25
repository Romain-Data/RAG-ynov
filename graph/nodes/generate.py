from graph.state import GraphState


def generate_node(state: GraphState) -> GraphState:
    """Generate answer using Mammouth LLM with retrieved context."""
    # TODO: Implement with Mammouth API
    # 1. Build prompt with retrieved chunks + question
    # 2. Call Mammouth chat completion
    # 3. Extract answer and build sources list
    return {"answer": "", "sources": []}