"""Chainlit handlers: login, history of a conversation, and one answer per message.

Loaded by Chainlit itself (chat/mount.py), hence the single file of @cl.* handlers. The
heavy lifting is in graph/chat.py (the RAG with history), chat/accounts.py (login) and
chat/messages.py (history and sources).
"""
import asyncio
import logging

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from chat import accounts
from chat.db import sqlalchemy_url
from chat.messages import history_from_steps, with_sources
from graph.chat import get_chat_graph

logger = logging.getLogger(__name__)

GREETING = (
    "Bonjour ! Posez-moi vos questions sur les formations Ynov : programmes, campus, "
    "admission, tarifs. Je garde le fil de la conversation, vous pouvez enchaîner avec des "
    "relances.\n\n[Supprimer mon compte](/compte/suppression)"
)
ERROR_MESSAGE = (
    "Désolé, je n'ai pas pu répondre à cause d'un problème technique. Réessayez dans un "
    "instant."
)


@cl.data_layer
def get_data_layer() -> SQLAlchemyDataLayer:
    return SQLAlchemyDataLayer(conninfo=sqlalchemy_url())


@cl.password_auth_callback
async def authenticate(username: str, password: str) -> cl.User | None:
    # argon2 takes tens of milliseconds: keep it off the event loop
    pseudo = await asyncio.to_thread(accounts.authenticate, username, password)
    return cl.User(identifier=pseudo, metadata={"provider": "credentials"}) if pseudo else None


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("history", [])
    await cl.Message(content=GREETING).send()


@cl.on_chat_resume
async def resume(thread: dict) -> None:
    cl.user_session.set("history", history_from_steps(thread["steps"], skip=GREETING))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    history: list[dict] = cl.user_session.get("history") or []
    history = [*history, {"role": "user", "content": message.content}]
    try:
        result = await get_chat_graph().ainvoke({"messages": history})
    except Exception:
        logger.exception("The chat graph failed")
        await cl.Message(content=ERROR_MESSAGE).send()
        return  # the question is not kept in the history: the user can ask again
    answer = result.get("answer", "").strip()
    cl.user_session.set("history", [*history, {"role": "assistant", "content": answer}])
    await cl.Message(content=with_sources(answer, result.get("sources", []))).send()


