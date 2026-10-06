"""Greetings and thanks are answered without search nor LLM (EC-16)."""

from unittest.mock import patch

import pytest

from graph.builder import build_graph
from graph.chat import build_chat_graph
from graph.nodes.smalltalk import GREETING_REPLY, THANKS_REPLY, smalltalk_reply


@pytest.mark.parametrize(
    "text", ["Bonjour", "bonjour !", "Salut", "Bonsoir à tous", "Hello", "Coucou"]
)
def test_greetings_get_the_presentation(text: str) -> None:
    assert smalltalk_reply(text) == GREETING_REPLY


@pytest.mark.parametrize(
    "text",
    [
        "Merci",
        "Merci beaucoup !",
        "Un grand merci pour votre aide",
        "D'accord, super.",
        "Ok merci",
        "Très bien",
        "Parfait, merci !",
        "Au revoir",
        "À bientôt",
        "Bonne journée",
    ],
)
def test_thanks_and_closings_get_a_short_reply(text: str) -> None:
    assert smalltalk_reply(text) == THANKS_REPLY


@pytest.mark.parametrize(
    "text",
    [
        "Combien coûte le Mastère IA ?",
        "Merci, et à Lyon ?",
        "Bonjour, combien coûte un BTS ?",
        "Super formation ?",
        "C'est quoi Ynov ?",
        "Et à Lyon ?",
        "Combien de temps dure le Bachelor Informatique ?",
        "Quel est le meilleur langage ?",
        "",
        "!!!",
        "tres",
        "et pour votre aide",
    ],
)
def test_a_question_or_a_word_without_courtesy_is_not_smalltalk(text: str) -> None:
    assert smalltalk_reply(text) is None


def test_the_question_graph_answers_without_retrieval_nor_llm() -> None:
    with (
        patch("graph.nodes.retrieve.search") as search,
        patch("graph.nodes.generate.chat_completion") as llm,
    ):
        state = build_graph().invoke({"question": "Bonjour"})
    assert state["answer"] == GREETING_REPLY
    assert state["sources"] == [] and state["grade"] == "ok"
    search.assert_not_called()
    llm.assert_not_called()


def test_the_chat_graph_thanks_after_an_answer_without_any_llm_call() -> None:
    messages = [
        {"role": "user", "content": "Combien de temps dure le Bachelor Informatique ?"},
        {"role": "assistant", "content": "3 ans."},
        {"role": "user", "content": "Merci beaucoup !"},
    ]
    with (
        patch("graph.nodes.retrieve.search") as search,
        patch("graph.nodes.condense.chat_completion") as condense,
        patch("graph.nodes.generate.chat_completion") as llm,
    ):
        state = build_chat_graph().invoke({"messages": messages})
    assert state["answer"] == THANKS_REPLY
    search.assert_not_called()
    condense.assert_not_called()
    llm.assert_not_called()
