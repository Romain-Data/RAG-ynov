"""Tests for the conversation graph (graph/chat.py) and its condense step."""

from unittest.mock import MagicMock, patch

import httpx

from graph.chat import MAX_HISTORY_MESSAGES, get_chat_graph, prepare_node
from graph.nodes.condense import condense_node


def _llm_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _mock_http(mock_httpx_cls, *contents: str) -> MagicMock:
    """Make httpx.Client().post return the given contents one after the other."""
    client = MagicMock()
    client.post.side_effect = [_llm_response(c) for c in contents]
    mock_httpx_cls.return_value.__enter__.return_value = client
    return client


def _point(score: float = 0.8) -> MagicMock:
    point = MagicMock()
    point.payload = {"text": "doc text", "source": "faq.md", "page": None, "section": "S"}
    point.score = score
    return point


class TestPrepareNode:
    def test_first_question_has_no_history(self):
        result = prepare_node({"messages": [{"role": "user", "content": "Bonjour"}]})
        assert result["question"] == "Bonjour"
        assert result["history"] == []

    def test_splits_last_question_from_history(self):
        messages = [
            {"role": "user", "content": "Combien coûte le Bachelor ?"},
            {"role": "assistant", "content": "8 900 €"},
            {"role": "user", "content": "Et le Mastère ?"},
        ]
        result = prepare_node({"messages": messages})
        assert result["question"] == "Et le Mastère ?"
        assert result["history"] == messages[:2]

    def test_keeps_only_the_last_messages(self):
        messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(21)
        ]
        result = prepare_node({"messages": messages})
        assert len(result["history"]) == MAX_HISTORY_MESSAGES
        assert result["history"][-1]["content"] == "19"

    def test_no_user_message_gives_empty_question(self):
        assert prepare_node({"messages": []})["question"] == ""
        assert prepare_node({"messages": [{"role": "assistant", "content": "x"}]})["question"] == ""


class TestCondenseNode:
    @patch("graph.nodes.condense.httpx.Client")
    def test_no_history_means_no_llm_call(self, mock_httpx_cls):
        result = condense_node({"question": "Combien ?", "history": []})
        assert result == {"rewritten": None}
        mock_httpx_cls.assert_not_called()

    @patch("graph.nodes.condense.httpx.Client")
    def test_rewrites_with_history(self, mock_httpx_cls):
        client = _mock_http(mock_httpx_cls, "  Le BTS ERA est-il proposé à Lyon ?  ")
        result = condense_node(
            {
                "question": "Et à Lyon ?",
                "history": [
                    {"role": "user", "content": "Où peut-on suivre le BTS ERA ?"},
                    {"role": "assistant", "content": "À Strasbourg."},
                ],
            }
        )
        assert result["rewritten"] == "Le BTS ERA est-il proposé à Lyon ?"
        sent = client.post.call_args.kwargs["json"]["messages"][1]["content"]
        assert "BTS ERA" in sent and "Et à Lyon ?" in sent

    @patch("graph.nodes.condense.httpx.Client")
    def test_llm_failure_keeps_the_original_question(self, mock_httpx_cls):
        client = MagicMock()
        client.post.side_effect = httpx.ConnectError("down")
        mock_httpx_cls.return_value.__enter__.return_value = client
        result = condense_node(
            {"question": "Et à Lyon ?", "history": [{"role": "user", "content": "x"}]}
        )
        assert result == {"rewritten": None}


class TestChatGraph:
    """httpx.Client is one object shared by every node: a single mock answers the LLM
    calls in order (rewrite first, then generation)."""

    def test_singleton(self):
        assert get_chat_graph() is get_chat_graph()

    @patch("graph.nodes.generate.httpx.Client")
    @patch("graph.nodes.retrieve.embed_query", return_value=[0.1] * 384)
    @patch("graph.nodes.retrieve.get_qdrant_client")
    def test_first_question_skips_condense(self, mock_qdrant, mock_embed, mock_httpx_cls):
        mock_qdrant.return_value.query_points.return_value = MagicMock(points=[_point()])
        client = _mock_http(mock_httpx_cls, "Réponse")

        result = get_chat_graph().invoke(
            {"messages": [{"role": "user", "content": "Combien coûte le BTS ?"}]}
        )
        assert result["answer"] == "Réponse"
        assert client.post.call_count == 1  # generation only, no rewrite
        mock_embed.assert_called_once_with("Combien coûte le BTS ?")

    @patch("graph.nodes.generate.httpx.Client")
    @patch("graph.nodes.retrieve.embed_query", return_value=[0.1] * 384)
    @patch("graph.nodes.retrieve.get_qdrant_client")
    def test_follow_up_is_searched_through_its_rewrite(
        self, mock_qdrant, mock_embed, mock_httpx_cls
    ):
        mock_qdrant.return_value.query_points.return_value = MagicMock(points=[_point()])
        client = _mock_http(
            mock_httpx_cls, "Le BTS ERA est-il proposé à Lyon ?", "Non, seulement à Strasbourg."
        )

        result = get_chat_graph().invoke(
            {
                "messages": [
                    {"role": "user", "content": "Où peut-on suivre le BTS ERA ?"},
                    {"role": "assistant", "content": "À Strasbourg."},
                    {"role": "user", "content": "Et à Lyon ?"},
                ]
            }
        )
        assert result["answer"] == "Non, seulement à Strasbourg."
        mock_embed.assert_called_once_with("Le BTS ERA est-il proposé à Lyon ?")
        sent = client.post.call_args_list[1].kwargs["json"]["messages"]
        # system, the 2 history messages, then the prompt with the standalone question
        assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
        assert "Le BTS ERA est-il proposé à Lyon ?" in sent[-1]["content"]

    @patch("graph.nodes.generate.httpx.Client")
    @patch("graph.nodes.retrieve.embed_query", return_value=[0.1] * 384)
    @patch("graph.nodes.retrieve.get_qdrant_client")
    def test_refuses_when_nothing_relevant(self, mock_qdrant, mock_embed, mock_httpx_cls):
        mock_qdrant.return_value.query_points.return_value = MagicMock(points=[])
        client = _mock_http(mock_httpx_cls, "Question reformulée")
        result = get_chat_graph().invoke(
            {
                "messages": [
                    {"role": "user", "content": "a"},
                    {"role": "assistant", "content": "b"},
                    {"role": "user", "content": "c"},
                ]
            }
        )
        assert result["grade"] == "refuse"
        assert result["sources"] == []
        assert client.post.call_count == 1  # the rewrite only: refused before generation
