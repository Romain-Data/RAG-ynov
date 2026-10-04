"""The LLM call: retries on 429 and 5xx, no retry on budget or bad key, clean failure."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from graph import llm

OK = {"choices": [{"message": {"content": "réponse"}}]}


def _response(status: int, body: str = "", headers: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://llm.test/chat/completions")
    if status == 200:
        return httpx.Response(200, json=OK, request=request)
    return httpx.Response(status, text=body, headers=headers or {}, request=request)


def _client(*outcomes: httpx.Response | Exception) -> MagicMock:
    """An httpx.Client whose successive post() calls give these outcomes."""
    client = MagicMock()

    def post(*_args: object, **_kwargs: object) -> httpx.Response:
        outcome = outcomes[client.post.call_count - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client.post.side_effect = post
    return client


@pytest.fixture
def sleeps():
    with patch.object(llm.time, "sleep") as sleep:
        yield sleep


def _call(client: MagicMock) -> dict:
    with patch.object(llm.httpx, "Client") as cls:
        cls.return_value.__enter__.return_value = client
        return llm.chat_completion({"model": "m"})


def test_success_needs_one_call(sleeps) -> None:
    client = _client(_response(200))
    assert _call(client) == OK
    assert client.post.call_count == 1 and not sleeps.called


def test_429_is_retried_then_succeeds(sleeps) -> None:
    client = _client(_response(429, "Too Many Requests"), _response(200))
    assert _call(client) == OK
    assert client.post.call_count == 2
    sleeps.assert_called_once_with(llm.BACKOFF_S[0])


def test_the_wait_follows_retry_after_but_is_capped(sleeps) -> None:
    client = _client(
        _response(429, headers={"retry-after": "4"}),
        _response(503, headers={"retry-after": "999"}),
        _response(200),
    )
    assert _call(client) == OK
    assert [c.args[0] for c in sleeps.call_args_list] == [4.0, llm.MAX_RETRY_AFTER_S]


def test_gives_up_after_three_attempts(sleeps) -> None:
    client = _client(*[_response(503)] * 3)
    with pytest.raises(llm.LLMUnavailableError):
        _call(client)
    assert client.post.call_count == llm.MAX_ATTEMPTS and sleeps.call_count == 2


def test_an_exhausted_budget_is_not_retried(sleeps) -> None:
    client = _client(_response(429, "Budget has been exceeded"))
    with pytest.raises(llm.LLMUnavailableError):
        _call(client)
    assert client.post.call_count == 1 and not sleeps.called


@pytest.mark.parametrize("status", [400, 401, 404])
def test_client_errors_are_not_retried(sleeps, status: int) -> None:
    client = _client(_response(status))
    with pytest.raises(llm.LLMUnavailableError):
        _call(client)
    assert client.post.call_count == 1


def test_a_read_timeout_is_not_retried(sleeps) -> None:
    client = _client(httpx.ReadTimeout("slow"))
    with pytest.raises(llm.LLMUnavailableError):
        _call(client)
    assert client.post.call_count == 1


def test_a_connection_error_is_retried(sleeps) -> None:
    client = _client(httpx.ConnectError("refused"), _response(200))
    assert _call(client) == OK


def test_query_answers_503_when_the_llm_is_down(client) -> None:
    """POST /api/query used to answer a 500 with a stack trace."""
    graph = MagicMock()
    graph.ainvoke = MagicMock(side_effect=llm.LLMUnavailableError("429"))

    async def fail(_state: dict) -> dict:
        raise llm.LLMUnavailableError("429")

    graph.ainvoke = fail
    with patch("app.api.query.get_graph", return_value=graph):
        resp = client.post("/api/query", json={"question": "Combien coûte le BTS ERA ?"})
    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "10"
    assert "indisponible" in resp.json()["detail"]
