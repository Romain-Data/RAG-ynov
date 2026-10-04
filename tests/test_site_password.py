"""The optional site password: HTTP and WebSocket, health exempt, off by default."""
import base64
import secrets
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.site_password import SitePasswordMiddleware

# Random at each run: no password literal in the repository
PASSWORD = secrets.token_urlsafe(16)


def _basic(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/page")
    async def page() -> dict:
        return {"page": True}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    app.add_middleware(SitePasswordMiddleware, password=PASSWORD)
    return TestClient(app)


def test_refuses_without_credentials(client: TestClient) -> None:
    resp = client.get("/page")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("Basic")


@pytest.mark.parametrize(
    "headers",
    [
        _basic("preprod", "wrong"),
        _basic("someone", PASSWORD),
        _basic("preprod", ""),
        {"Authorization": "Bearer abc"},
        {"Authorization": "Basic !!!not-base64!!!"},
        {"Authorization": "Basic " + base64.b64encode(b"no-colon").decode()},
    ],
)
def test_refuses_bad_credentials(client: TestClient, headers: dict[str, str]) -> None:
    assert client.get("/page", headers=headers).status_code == 401


def test_accepts_good_credentials(client: TestClient) -> None:
    resp = client.get("/page", headers=_basic("preprod", PASSWORD))
    assert resp.status_code == 200 and resp.json() == {"page": True}


def test_password_may_contain_a_colon() -> None:
    app = FastAPI()

    @app.get("/page")
    async def page() -> dict:
        return {}

    with_colon = f"{PASSWORD}:{PASSWORD}"
    app.add_middleware(SitePasswordMiddleware, password=with_colon)
    assert TestClient(app).get("/page", headers=_basic("preprod", with_colon)).status_code == 200


def test_health_is_exempt(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200


def test_websocket_refused_without_credentials(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws"):
        pass


def test_websocket_accepted_with_credentials(client: TestClient) -> None:
    with client.websocket_connect("/ws", headers=_basic("preprod", PASSWORD)) as ws:
        assert ws.receive_text() == "hello"


def test_main_app_has_no_password_by_default(client: TestClient) -> None:
    """Production sets no SITE_PASSWORD: the real app answers without credentials."""
    from app.main import app

    names = [m.cls.__name__ for m in app.user_middleware]
    assert "SitePasswordMiddleware" not in names


def test_eval_sends_the_password_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from eval import e2e

    response = MagicMock()
    response.json.return_value = {"answer": "x"}
    with patch.object(e2e.httpx, "post", return_value=response) as post:
        monkeypatch.setenv("EVAL_SITE_PASSWORD", PASSWORD)
        e2e.ask("https://example.test", "q ?")
        assert post.call_args.kwargs["auth"] == ("preprod", PASSWORD)
        monkeypatch.delenv("EVAL_SITE_PASSWORD")
        e2e.ask("https://example.test", "q ?")
        assert post.call_args.kwargs["auth"] is None
