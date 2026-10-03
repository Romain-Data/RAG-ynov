"""Conversation graph: the RAG pipeline with a chat history.

Same retrieve / grade / generate / refuse nodes as graph/builder.py, preceded by two
steps: `prepare` splits the messages into the last question and the history, and
`condense` rewrites the question so that a follow-up ("Et à Lyon ?") can be searched.

The graph keeps no state between calls: the caller sends the whole conversation as
`messages` ([{"role": "user" | "assistant", "content": ...}, ...], the last one being
the new question) and gets the answer for that last question.
"""
from langgraph.graph import END, StateGraph

from graph.builder import should_generate
from graph.nodes.condense import condense_node
from graph.nodes.generate import generate_node
from graph.nodes.grade import grade_node
from graph.nodes.refuse import refuse_node
from graph.nodes.retrieve import retrieve_node
from graph.state import GraphState

MAX_HISTORY_MESSAGES = 6  # the last 3 exchanges are enough to resolve a follow-up
MAX_HISTORY_CHARS = 1200  # per message: answers can be long and carry source lists


class ChatState(GraphState):
    messages: list[dict]


def prepare_node(state: ChatState) -> dict:
    """Last user message -> question; the messages before it -> history."""
    messages = state.get("messages") or []
    if not messages or messages[-1].get("role") != "user":
        return {"question": "", "history": [], "rewritten": None}
    previous = messages[:-1][-MAX_HISTORY_MESSAGES:]
    history = [
        {"role": m["role"], "content": m["content"][:MAX_HISTORY_CHARS]} for m in previous
    ]
    return {"question": messages[-1]["content"], "history": history, "rewritten": None}


def build_chat_graph():
    workflow = StateGraph(ChatState)
    workflow.add_node("prepare", prepare_node)
    workflow.add_node("condense", condense_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("refuse", refuse_node)

    workflow.set_entry_point("prepare")
    workflow.add_edge("prepare", "condense")
    workflow.add_edge("condense", "retrieve")
    workflow.add_edge("retrieve", "grade")
    workflow.add_conditional_edges(
        "grade", should_generate, {"generate": "generate", "refuse": "refuse"}
    )
    workflow.add_edge("generate", END)
    workflow.add_edge("refuse", END)
    return workflow.compile()


_chat_graph = None


def get_chat_graph():
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = build_chat_graph()
    return _chat_graph
