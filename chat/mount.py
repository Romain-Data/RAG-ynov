"""Mount the chat (Chainlit on /) and the account pages (/compte) on the API."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI

from app.core.config import settings

logger = logging.getLogger(__name__)

CHAT_DIR = Path(__file__).resolve().parent


def mount_chat(app: FastAPI) -> bool:
    """Returns False, and leaves the API as it is, when the chat is not configured.

    Chainlit refuses to start without a secret to sign its session cookies: mounting it
    unconditionally would take the whole API down on a deployment that lacks the variable.
    """
    if not settings.chainlit_auth_secret:
        logger.warning("CHAINLIT_AUTH_SECRET is not set: the chat interface is disabled")
        return False
    # Chainlit reads these when it is first imported: configuration and static files
    # live in chat/ (.chainlit/config.toml, public/), not in the project root.
    os.environ.setdefault("CHAINLIT_APP_ROOT", str(CHAT_DIR))
    os.environ["CHAINLIT_AUTH_SECRET"] = settings.chainlit_auth_secret

    from chainlit.utils import mount_chainlit

    from chat.routes import router

    app.include_router(router)
    mount_chainlit(app=app, target=str(CHAT_DIR / "app.py"), path="/")
    return True
