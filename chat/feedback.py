"""The thumbs under the answers of the chat (#19): Chainlit's, tied to the journal and guarded.

Chainlit shows "Utile / Pas utile" under the last message of each `on_message` run and
writes the choice to its `feedbacks` table through PUT /feedback (DELETE /feedback when it
is taken back). The feedback targets the run step, not the answer: the answer is the run's
child step, and its id is the message_id of the journal entry.

Chainlit checks none of what it receives: these routes, declared before Chainlit is mounted
(chat/mount.py), check it and then hand over to Chainlit's own handlers.
"""

import asyncio

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.server import UserParam
from chainlit.server import delete_feedback as chainlit_delete_feedback
from chainlit.server import update_feedback as chainlit_update_feedback
from chainlit.types import DeleteFeedbackRequest, Feedback, UpdateFeedbackRequest
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.security import rate_limit_feedback
from chat.db import db
from journal import store
from journal.store import MAX_COMMENT


class FeedbackDataLayer(SQLAlchemyDataLayer):
    """Chainlit's data layer, which also copies each feedback to the journal of the answers."""

    async def upsert_feedback(self, feedback: Feedback) -> str:
        feedback_id = await super().upsert_feedback(feedback)
        await asyncio.to_thread(
            store.set_feedback, feedback.forId, feedback.value, feedback.comment
        )
        return feedback_id

    async def delete_feedback(self, feedback_id: str) -> bool:
        found = await self.execute_sql(
            'SELECT "forId" FROM feedbacks WHERE "id" = :id', {"id": feedback_id}
        )
        deleted = await super().delete_feedback(feedback_id)
        if isinstance(found, list) and found:
            await asyncio.to_thread(store.clear_feedback, found[0]["forId"])
        return deleted


def _run(run_id: str) -> tuple[str, str] | None:
    """(thread, owner) of an `on_message` run, None for any other step or an unknown id."""
    with db() as conn:
        row = conn.execute(
            "SELECT s.threadId, t.userIdentifier FROM steps s JOIN threads t ON t.id = s.threadId "
            "WHERE s.id = ? AND s.type = 'run' AND s.name = 'on_message'",
            (run_id,),
        ).fetchone()
    return (row[0], row[1]) if row else None


def _feedback_of(run_id: str) -> str | None:
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM feedbacks WHERE forId = ? ORDER BY rowid LIMIT 1", (run_id,)
        ).fetchone()
    return row[0] if row else None


def _feedback_owner(feedback_id: str) -> str | None:
    with db() as conn:
        row = conn.execute(
            "SELECT t.userIdentifier FROM feedbacks f JOIN steps s ON s.id = f.forId "
            "JOIN threads t ON t.id = s.threadId WHERE f.id = ?",
            (feedback_id,),
        ).fetchone()
    return row[0] if row else None


def _identifier(user: object) -> str:
    identifier = getattr(user, "identifier", None)
    if not isinstance(identifier, str) or not identifier:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return identifier


def _not_found() -> HTTPException:
    """The same answer whether the step does not exist or belongs to someone else."""
    return HTTPException(status_code=404, detail="Réponse introuvable")


router = APIRouter(include_in_schema=False, dependencies=[Depends(rate_limit_feedback)])


@router.put("/feedback")
async def update_feedback(
    request: Request, update: UpdateFeedbackRequest, current_user: UserParam
) -> JSONResponse:
    feedback = update.feedback
    if feedback.comment and len(feedback.comment) > MAX_COMMENT:
        raise HTTPException(
            status_code=422, detail=f"Commentaire trop long ({MAX_COMMENT} caractères au plus)"
        )
    run = await asyncio.to_thread(_run, feedback.forId)
    if run is None or run[1] != _identifier(current_user):
        raise _not_found()
    if feedback.threadId and feedback.threadId != run[0]:
        raise _not_found()
    feedback.threadId = run[0]
    # One feedback per answer: a second one updates the first. An id sent by the browser is
    # never trusted: Chainlit upserts by id and would rewrite somebody else's feedback.
    feedback.id = await asyncio.to_thread(_feedback_of, feedback.forId)
    response: JSONResponse = await chainlit_update_feedback(request, update, current_user)
    return response


@router.delete("/feedback")
async def delete_feedback(
    request: Request, payload: DeleteFeedbackRequest, current_user: UserParam
) -> JSONResponse:
    owner = await asyncio.to_thread(_feedback_owner, payload.feedbackId)
    if owner is None or owner != _identifier(current_user):
        raise _not_found()
    response: JSONResponse = await chainlit_delete_feedback(request, payload, current_user)
    return response
