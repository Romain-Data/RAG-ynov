"""The call to the LLM (Mammouth, OpenAI-compatible chat completions), shared by the nodes.

Mammouth answers 429 when a model is asked too fast, and the odd 5xx: those are retried a
couple of times, since the next attempt usually works. Anything else, or a LLM that stays
unavailable, raises LLMUnavailableError, so that callers can show a clean message instead of
a stack trace.
"""

import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_S = (1.0, 3.0)  # wait before the 2nd and the 3rd attempt
MAX_RETRY_AFTER_S = 10.0  # longest wait asked for by the server that is honoured
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class LLMUnavailableError(RuntimeError):
    """The LLM could not answer (rate limit, budget, outage, timeout, bad key...)."""


def _wait_before_retry(attempt: int, response: httpx.Response | None) -> float:
    retry_after = response.headers.get("retry-after") if response is not None else None
    try:
        return min(float(retry_after), MAX_RETRY_AFTER_S) if retry_after else BACKOFF_S[attempt]
    except ValueError:  # an HTTP date: not worth parsing here
        return BACKOFF_S[attempt]


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        if response.status_code not in RETRYABLE_STATUSES:
            return False
        # An exhausted budget also answers 429, and waiting does not fix it
        return not (response.status_code == 429 and "budget" in response.text.lower())
    # Connection failures are retried; a read timeout is not (30 s each time)
    return isinstance(exc, httpx.TransportError) and not isinstance(exc, httpx.ReadTimeout)


def chat_completion(payload: dict, timeout: float = 30.0) -> dict:
    """POST the payload to /chat/completions and return the JSON answer."""
    url = f"{settings.mammouth_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.mammouth_api_key}",
        "Content-Type": "application/json",
    }
    for attempt in range(MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data: dict = resp.json()
                return data
        except httpx.HTTPError as exc:
            last_attempt = attempt == MAX_ATTEMPTS - 1
            if last_attempt or not _is_retryable(exc):
                raise LLMUnavailableError(f"{type(exc).__name__}: {exc}") from exc
            response = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
            wait = _wait_before_retry(attempt, response)
            logger.warning("LLM call failed (%s), retrying in %.0f s", exc, wait)
            time.sleep(wait)
    raise AssertionError("unreachable")  # the loop always returns or raises
