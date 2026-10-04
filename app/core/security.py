"""Security middleware: rate limiting + CORS."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

# In-memory limiter — fine for a single API instance.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)


def add_security_middleware(app: FastAPI) -> None:
    """Attach CORS and the slowapi limiter to the FastAPI app."""
    origins = settings.cors_origin_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Ingest-Key"],
    )

    app.state.limiter = limiter
    # slowapi types its handler for RateLimitExceeded, Starlette expects Exception
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# FastAPI dependencies: each one is a slowapi-decorated Request handler.
# Declared at module level so FastAPI can inspect them at import time.


@limiter.limit(f"{settings.rate_limit_query}/minute")
def rate_limit_query(request: Request) -> None:
    """Rate limit for /query (default 30 req/min/IP)."""


@limiter.limit(f"{settings.rate_limit_ingest}/minute")
def rate_limit_ingest(request: Request) -> None:
    """Rate limit for /ingest (default 5 req/min/IP)."""


@limiter.limit(f"{settings.rate_limit_health}/minute")
def rate_limit_health(request: Request) -> None:
    """Rate limit for /health and / (default 120 req/min/IP)."""


@limiter.limit(f"{settings.rate_limit_account}/minute")
def rate_limit_account(request: Request) -> None:
    """Rate limit for the account pages: sign-up, recovery, deletion (default 20 req/min/IP)."""
