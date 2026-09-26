"""Tests for the RAG Ynov API."""
from unittest.mock import AsyncMock, patch


class TestHealthEndpoint:
    def test_health_without_qdrant(self, client):
        """Health returns degraded when Qdrant is unreachable."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert data["embedding_model"] == (
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        assert data["chat_model"] == "mistral-medium-3-5"

    def test_health_root(self, client):
        """Root endpoint returns API metadata."""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "RAG Ynov"
        assert data["version"] == "0.1.0"


class TestQueryEndpoint:
    @patch("app.api.query.get_graph")
    def test_query_ok(self, mock_get_graph, client):
        """Query returns answer and sources when grade is ok."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "question": "Quels sont les frais de scolarité ?",
            "grade": "ok",
            "answer": "Les frais varient selon le niveau.",
            "sources": [
                {"source": "admissions_faq.md", "page": 1, "section": None, "score": 0.85}
            ],
            "retrieved": [],
        }
        mock_get_graph.return_value = mock_graph

        resp = client.post(
            "/api/query", json={"question": "Quels sont les frais de scolarité ?"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Les frais varient selon le niveau."
        assert data["grade"] == "ok"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "admissions_faq.md"
        mock_graph.ainvoke.assert_awaited_once()

    @patch("app.api.query.get_graph")
    def test_query_refuse_empty_retrieved(self, mock_get_graph, client):
        """Query returns refuse when no relevant docs found."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "question": "Test",
            "grade": "refuse",
            "answer": "Je n'ai pas trouvé d'information pertinente...",
            "sources": [],
            "retrieved": [],
        }
        mock_get_graph.return_value = mock_graph

        resp = client.post("/api/query", json={"question": "Question sans réponse"})
        assert resp.status_code == 200
        assert resp.json()["grade"] == "refuse"
        assert resp.json()["sources"] == []

    def test_query_empty_question(self, client):
        """Empty question should be rejected."""
        resp = client.post("/api/query", json={"question": ""})
        assert resp.status_code == 422

    def test_query_missing_question(self, client):
        """Missing question field should be rejected."""
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422


class TestIngestEndpoint:
    def test_ingest_unauthorized(self, client):
        """Ingest without key should return 401."""
        resp = client.post("/api/ingest", json={})
        assert resp.status_code == 401

    def test_ingest_wrong_key(self, client):
        """Ingest with wrong key should return 401."""
        resp = client.post(
            "/api/ingest",
            headers={"X-Ingest-Key": "wrong"},
            json={},
        )
        assert resp.status_code == 401
