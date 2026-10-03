import logging

import httpx

from app.core.config import settings
from graph.state import GraphState

logger = logging.getLogger(__name__)

CONDENSE_PROMPT = (
    "Tu reformules la dernière question d'un utilisateur en une question autonome, "
    "compréhensible sans l'historique de la conversation.\n"
    "Règles : remplace les références (« et à Lyon ? », « combien ça coûte ? », « il », "
    "« cette formation ») par ce qu'elles désignent dans l'historique ; garde tels quels "
    "les noms de formations, de villes et les chiffres ; n'ajoute aucune information qui "
    "n'est pas dans l'historique ; si la question est déjà autonome, recopie-la telle "
    "quelle. Réponds uniquement par la question reformulée, en français."
)


def _transcript(history: list[dict], question: str) -> str:
    lines = []
    for turn in history:
        speaker = "Utilisateur" if turn["role"] == "user" else "Assistant"
        lines.append(f"{speaker} : {turn['content']}")
    return "Historique :\n" + "\n".join(lines) + f"\n\nDernière question : {question}"


def condense_node(state: GraphState) -> dict:
    """Rewrite a follow-up question into a standalone one, using the chat history.

    Without history there is nothing to resolve: no LLM call, the question is kept.
    If the LLM call fails the question is kept too, so the search can still run.
    """
    history = state.get("history") or []
    question = state.get("question", "")
    if not history or not question:
        return {"rewritten": None}

    payload = {
        "model": settings.mammouth_chat_model,
        "messages": [
            {"role": "system", "content": CONDENSE_PROMPT},
            {"role": "user", "content": _transcript(history, question)},
        ],
        "temperature": 0.0,
        "max_tokens": 150,
    }
    headers = {
        "Authorization": f"Bearer {settings.mammouth_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{settings.mammouth_base_url}/chat/completions", headers=headers, json=payload
            )
            resp.raise_for_status()
            rewritten = resp.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.warning("Question rewriting failed, keeping the original: %s", exc)
        return {"rewritten": None}
    return {"rewritten": rewritten or None}
