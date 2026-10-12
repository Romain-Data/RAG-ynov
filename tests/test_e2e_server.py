"""What eval.e2e records about the server it asks (#16): /api/health before and after."""

import json
import sys
from pathlib import Path

import httpx
import pytest

from eval import e2e, results

URL = "https://rag-preprod.example"
HEALTH = {
    "status": "ok",
    "qdrant": "ok",
    "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "chat_model": "mammouth-recommended",
    "collection": "ynov_rag_v4",
    "grade_threshold": 0.47,
    "version": "61c1240",
}


def _response(status: int, **kwargs) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("GET", f"{URL}/api/health"), **kwargs)


class TestServerInfo:
    def test_reads_health(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = []

        def get(url: str, **kwargs) -> httpx.Response:
            calls.append((url, kwargs))
            return _response(200, json=HEALTH)

        monkeypatch.setattr(e2e.httpx, "get", get)
        monkeypatch.setenv("EVAL_SITE_PASSWORD", "from-the-environment")
        assert e2e.server_info(URL) == HEALTH
        assert calls[0][0] == f"{URL}/api/health"
        assert calls[0][1]["auth"] == ("preprod", "from-the-environment")

    @pytest.mark.parametrize(
        "answer",
        [
            httpx.ConnectError("refused"),
            _response(503, json={"detail": "down"}),
            _response(200, text="<html>not json</html>"),
            _response(200, json=["not", "a", "dict"]),
        ],
    )
    def test_none_when_the_server_does_not_tell(
        self, monkeypatch: pytest.MonkeyPatch, answer: object
    ) -> None:
        def get(url: str, **kwargs) -> httpx.Response:
            if isinstance(answer, Exception):
                raise answer
            assert isinstance(answer, httpx.Response)
            return answer

        monkeypatch.setattr(e2e.httpx, "get", get)
        assert e2e.server_info(URL) is None


class TestServerConfig:
    def test_named_like_a_local_run(self) -> None:
        config, warning = e2e.server_config(URL, HEALTH, dict(HEALTH))
        assert warning is None
        assert config == {
            "url": URL,
            "server": HEALTH,
            "llm_model": "mammouth-recommended",
            "embedding_model": HEALTH["embedding_model"],
            "collection": "ynov_rag_v4",
            "grade_threshold": 0.47,
            "server_version": "61c1240",
        }

    def test_change_during_the_run_is_reported(self) -> None:
        after = {**HEALTH, "collection": "ynov_rag_v5", "status": "degraded"}
        config, warning = e2e.server_config(URL, HEALTH, after)
        assert config["collection"] == "ynov_rag_v4"  # what answered the first questions
        assert config["server_after"] == after
        # The status is not a configuration: only the collection is named
        assert warning == (
            "Configuration du serveur changée pendant le passage "
            "(collection : ynov_rag_v4 → ynov_rag_v5)."
        )

    def test_health_missing_before_uses_after(self) -> None:
        config, warning = e2e.server_config(URL, None, HEALTH)
        assert config["llm_model"] == "mammouth-recommended" and warning is None

    def test_health_never_answered(self) -> None:
        config, warning = e2e.server_config(URL, None, None)
        assert warning is None
        assert config["server"] is None and config["llm_model"] is None
        assert "injoignable" in e2e.describe_server(config)

    def test_describe(self) -> None:
        config, _ = e2e.server_config(URL, HEALTH, None)
        assert e2e.describe_server(config) == (
            "Serveur : modèle mammouth-recommended, collection ynov_rag_v4, seuil 0.47, "
            "commit 61c1240."
        )
        config, _ = e2e.server_config(URL, {**HEALTH, "version": None}, None)
        assert e2e.describe_server(config).endswith("commit ?.")


def test_a_saved_run_records_the_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole command on a server, without network: health changes during the run."""
    healths = iter([HEALTH, {**HEALTH, "chat_model": "autre-modele"}])
    refused = {"answer": "Je n'ai pas trouvé.", "sources": [], "grade": "refuse"}
    monkeypatch.setattr(e2e, "server_info", lambda _url: next(healths))
    monkeypatch.setattr(e2e, "ask", lambda _url, _question: (refused, 0.1, None))
    monkeypatch.setattr(e2e.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(results, "RESULTS_DIR", tmp_path)
    summary = tmp_path / "summary.md"
    argv = ["e2e", "--url", URL, "--environment", "preprod", "--ids", "q17"]
    argv += ["--save", "essai", "--notes", "Note.", "--summary", str(summary)]
    monkeypatch.setattr(sys, "argv", argv)

    e2e.main()

    run = json.loads(next(tmp_path.glob("*_essai.json")).read_text(encoding="utf-8"))
    assert run["config"]["llm_model"] == "mammouth-recommended"
    assert run["config"]["server_after"]["chat_model"] == "autre-modele"
    assert run["notes"].startswith("Note. Configuration du serveur changée")
    assert run["question_set"] == results.QUESTION_SET
    assert [r["verdict"] for r in run["results"]] == ["correct"]  # q17 refused: expected
    assert "Serveur : modèle mammouth-recommended" in summary.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert out.startswith("Serveur : modèle mammouth-recommended")
    assert "Configuration du serveur changée" in out
