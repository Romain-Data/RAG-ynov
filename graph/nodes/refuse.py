from graph.state import GraphState
from app.schemas import Source


def refuse_node(state: GraphState) -> GraphState:
    """Return a polite refusal when no relevant documents found."""
    return {
        "answer": "Je n'ai pas trouvé d'information pertinente dans les documents Ynov pour répondre à votre question.",
        "sources": [],
        "grade": "refuse",
    }