"""Tests for the LangGraph RAG pipeline."""

from unittest.mock import MagicMock, patch

from graph.builder import get_graph


class TestGraphBuilder:
    def test_graph_singleton(self):
        """get_graph returns a compiled LangGraph."""
        graph = get_graph()
        assert graph is not None
        assert get_graph() is graph

    def test_graph_type(self):
        """The compiled graph should have an ainvoke method."""
        graph = get_graph()
        assert hasattr(graph, "ainvoke")
        assert hasattr(graph, "invoke")


class TestGradeNode:
    def test_grade_empty_retrieved(self):
        """Empty retrieved list should grade as 'refuse'."""
        from graph.nodes.grade import grade_node

        result = grade_node({"question": "test", "retrieved": []})
        assert result["grade"] == "refuse"

    def test_grade_below_threshold(self):
        """Scores below 0.5 should grade as 'refuse'."""
        from graph.nodes.grade import grade_node

        result = grade_node(
            {
                "question": "test",
                "retrieved": [{"text": "a", "score": 0.3}, {"text": "b", "score": 0.4}],
            }
        )
        assert result["grade"] == "refuse"

    def test_grade_above_threshold(self):
        """Max score >= 0.5 should grade as 'ok'."""
        from graph.nodes.grade import grade_node

        result = grade_node(
            {
                "question": "test",
                "retrieved": [{"text": "a", "score": 0.6}],
            }
        )
        assert result["grade"] == "ok"

    def test_grade_exact_threshold(self):
        """Score exactly 0.5 should grade as 'ok'."""
        from graph.nodes.grade import grade_node

        result = grade_node(
            {
                "question": "test",
                "retrieved": [{"text": "a", "score": 0.5}],
            }
        )
        assert result["grade"] == "ok"


class TestRefuseNode:
    def test_refuse_node_output(self):
        """Refuse node returns a polite message and empty sources."""
        from graph.nodes.refuse import refuse_node

        result = refuse_node({"question": "test", "grade": "refuse", "retrieved": []})
        assert result["grade"] == "refuse"
        assert "pertinente" in result["answer"].lower()
        assert result["sources"] == []


def _scored_point(text="test text", source="faq.md", page=1, score=0.8):
    point = MagicMock()
    point.payload = {"text": text, "source": source, "page": page}
    point.score = score
    return point


def _query_response(points):
    response = MagicMock()
    response.points = points
    return response


class TestRetrieveNode:
    def test_retrieve_empty_question(self):
        """Empty question returns empty retrieved without calling Qdrant."""
        from graph.nodes.retrieve import retrieve_node

        result = retrieve_node({"question": "", "retrieved": []})
        assert result["retrieved"] == []

    @patch("graph.nodes.retrieve.embed_query", return_value=[0.1] * 384)
    @patch("graph.nodes.retrieve.get_qdrant_client")
    def test_retrieve_with_results(self, mock_client, mock_embed):
        """Retrieve formats Qdrant payloads into retrieved dicts."""
        from graph.nodes.retrieve import retrieve_node

        mock_client.return_value.query_points.return_value = _query_response([_scored_point()])

        result = retrieve_node({"question": "test", "retrieved": []})
        assert len(result["retrieved"]) == 1
        assert result["retrieved"][0]["text"] == "test text"
        assert result["retrieved"][0]["score"] == 0.8
        assert result["retrieved"][0]["source"] == "faq.md"
        mock_embed.assert_called_once_with("test")


class TestGenerateNode:
    def test_generate_empty_retrieved(self):
        """Empty retrieved should return empty answer without calling the LLM."""
        from graph.nodes.generate import generate_node

        result = generate_node({"question": "test", "retrieved": []})
        assert result["answer"] == ""
        assert result["sources"] == []

    @patch("graph.nodes.generate.httpx.Client")
    def test_generate_builds_sources_and_calls_llm(self, mock_httpx_cls):
        """Generate calls Mammouth and maps retrieved chunks to sources."""
        from graph.nodes.generate import generate_node

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "  Les frais sont de 8900 €.  "}}]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_httpx_cls.return_value.__enter__.return_value = mock_client

        state = {
            "question": "Quels sont les frais ?",
            "retrieved": [
                {
                    "text": "1re année : 8 900 €",
                    "source": "admissions_faq.md",
                    "page": 1,
                    "section": None,
                    "score": 0.82,
                }
            ],
        }
        result = generate_node(state)
        assert result["answer"] == "Les frais sont de 8900 €."
        assert len(result["sources"]) == 1
        assert result["sources"][0]["source"] == "admissions_faq.md"
        assert result["sources"][0]["score"] == 0.82
        mock_client.post.assert_called_once()


class TestEndToEndGraph:
    @patch("graph.nodes.retrieve.embed_query", return_value=[0.1] * 384)
    @patch("graph.nodes.retrieve.get_qdrant_client")
    def test_full_graph_refuse(self, mock_client, mock_embed):
        """Full graph with no hits should refuse without calling the LLM."""
        mock_client.return_value.query_points.return_value = _query_response([])

        graph = get_graph()
        result = graph.invoke({"question": "test"})
        assert result["grade"] == "refuse"
        assert result["sources"] == []

    @patch("graph.nodes.generate.httpx.Client")
    @patch("graph.nodes.retrieve.embed_query", return_value=[0.1] * 384)
    @patch("graph.nodes.retrieve.get_qdrant_client")
    def test_full_graph_ok(self, mock_client, mock_embed, mock_httpx_cls):
        """Full graph with good scores should generate via Mammouth."""
        mock_client.return_value.query_points.return_value = _query_response(
            [_scored_point(text="doc text", score=0.8)]
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Réponse générée"}}]}
        mock_http = MagicMock()
        mock_http.post.return_value = mock_resp
        mock_httpx_cls.return_value.__enter__.return_value = mock_http

        graph = get_graph()
        result = graph.invoke({"question": "test"})
        assert result["grade"] == "ok"
        assert result["answer"] == "Réponse générée"
        mock_http.post.assert_called_once()
