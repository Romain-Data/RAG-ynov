"""Authentication of the admin pages: one password, a signed session cookie.

No HTTP Basic: the preprod already puts one in front of the whole site (a second one would
fight for the same Authorization header). The cookie holds its expiry and an HMAC of it; the
key is derived from ADMIN_PASSWORD, so changing the password logs everyone out, and nothing
is stored on the server.
"""

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlparse

from fastapi import Request

COOKIE = "admin_session"
SESSION_TTL_S = 8 * 3600
# Plain-http hosts where the Secure flag would only get in the way (local development)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def check_password(candidate: str, expected: str) -> bool:
    """Constant-time comparison; an empty expected password never matches."""
    return bool(expected) and secrets.compare_digest(candidate.encode(), expected.encode())


def _signature(password: str, expires: str) -> str:
    key = hashlib.sha256(b"admin-session:" + password.encode()).digest()
    return hmac.new(key, expires.encode(), hashlib.sha256).hexdigest()


def make_token(password: str, now: float | None = None) -> str:
    expires = str(int((time.time() if now is None else now) + SESSION_TTL_S))
    return f"{expires}.{_signature(password, expires)}"


def verify_token(password: str, token: str | None, now: float | None = None) -> bool:
    """True for a token signed with this password and not expired."""
    if not password or not token:
        return False
    expires, _, signature = token.partition(".")
    if not expires.isdigit() or not secrets.compare_digest(
        signature.encode(), _signature(password, expires).encode()
    ):
        return False
    return int(expires) > (time.time() if now is None else now)


def is_authenticated(request: Request, password: str) -> bool:
    return verify_token(password, request.cookies.get(COOKIE))


def cookie_is_secure(request: Request) -> bool:
    """Secure everywhere except plain http on localhost. Behind the proxy the request seen by
    the app may be http, hence the forwarded protocol."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    return scheme == "https" or request.url.hostname not in _LOCAL_HOSTS


def same_origin(request: Request) -> bool:
    """CSRF guard for the POSTs: a browser sends Origin on them, and it must be this host.
    Without Origin the request does not come from a browser form (SameSite=Strict covers the
    rest); the value "null" (sandboxed pages) is refused."""
    origin = request.headers.get("origin")
    if origin is None:
        return True
    netloc = urlparse(origin).netloc
    return bool(netloc) and netloc == request.headers.get("host", "")
