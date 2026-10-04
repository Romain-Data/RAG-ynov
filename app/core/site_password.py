"""Optional HTTP Basic password in front of the whole site (HTTP and WebSocket).

Used by the preprod, which is not meant for the public: Coolify's own basic auth does not
apply to docker-compose applications. Off unless SITE_PASSWORD is set, so production is
unchanged.
"""

import base64
import secrets
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# The Docker healthcheck (curl on localhost) and Coolify carry no credentials
EXEMPT_PATHS = ("/api/health",)


class SitePasswordMiddleware:
    """Pure ASGI middleware: a Starlette BaseHTTPMiddleware would not cover WebSockets,
    which carry the chat."""

    def __init__(self, app: ASGIApp, password: str, user: str = "preprod") -> None:
        self.app = app
        self.expected = (user.encode(), password.encode())

    def _authorized(self, scope: Scope) -> bool:
        for name, value in scope["headers"]:
            if name == b"authorization":
                scheme, _, token = value.partition(b" ")
                if scheme.lower() != b"basic":
                    return False
                try:
                    user, sep, password = base64.b64decode(token, validate=True).partition(b":")
                except ValueError:
                    return False
                # Evaluate both, so the check does not reveal which one was wrong
                user_ok = secrets.compare_digest(user, self.expected[0])
                password_ok = secrets.compare_digest(password, self.expected[1])
                return bool(sep) and user_ok and password_ok
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or scope["path"] in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        if self._authorized(scope):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            # Closing before accepting makes the handshake fail with a 403
            await send({"type": "websocket.close", "code": 1008})
            return
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b'Basic realm="RAG Ynov preprod", charset="UTF-8"'),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"x-robots-tag", b"noindex, nofollow"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"Authentication required"})
