from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from graph.nodes.generate import generate_node
from graph.nodes.grade import grade_node
from graph.nodes.refuse import refuse_node
from graph.nodes.retrieve import retrieve_node
from graph.nodes.smalltalk import route_after_smalltalk, smalltalk_node
from graph.state import GraphState


def should_generate(state: GraphState) -> str:
    """Route to generate or refuse based on grade."""
    return "generate" if state.get("grade") == "ok" else "refuse"


def build_graph() -> CompiledStateGraph:
    """Build and compile the RAG LangGraph."""
    workflow = StateGraph(GraphState)

    # Nodes
    workflow.add_node("smalltalk", smalltalk_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("refuse", refuse_node)

    # Edges
    workflow.set_entry_point("smalltalk")
    workflow.add_conditional_edges(
        "smalltalk",
        lambda state: route_after_smalltalk(state, "retrieve"),
        {"retrieve": "retrieve", "end": END},
    )
    workflow.add_edge("retrieve", "grade")
    workflow.add_conditional_edges(
        "grade",
        should_generate,
        {
            "generate": "generate",
            "refuse": "refuse",
        },
    )
    workflow.add_edge("generate", END)
    workflow.add_edge("refuse", END)

    return workflow.compile()


# Singleton instance (lazy)
_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
