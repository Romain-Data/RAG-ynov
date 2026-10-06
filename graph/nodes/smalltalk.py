"""Greetings and thanks: answered with a fixed sentence, without search or LLM call (EC-16).

The grading threshold compares a question with the corpus, and "Bonjour" or "Merci beaucoup !"
looks like no chunk: they were refused as if they were off-topic questions. Only a message made
of courtesy words alone is caught: any other word ("Merci, et à Lyon ?") sends it down the
normal path.
"""

import re
import unicodedata

from graph.state import GraphState

GREETING_WORDS = {"bonjour", "bonsoir", "salut", "coucou", "hello", "hey"}
THANKS_WORDS = {"merci", "beaucoup", "infiniment", "encore", "grand", "bien", "mille"}
# Closings, acknowledgements and the small words that go with them.
OTHER_WORDS = {
    "au", "revoir", "a", "bientot", "bye", "bonne", "journee", "soiree", "continuation",
    "ok", "okay", "d", "accord", "dac", "super", "parfait", "genial", "tres", "entendu",
    "compris", "top", "nickel", "cool", "ca", "marche", "c", "est", "note", "excellent",
    "impeccable", "vous", "toi", "aussi", "pour", "votre", "ton", "aide", "tout", "et",
    "un", "de", "rien", "tous", "toutes",
}  # fmt: skip
# At least one of these must be there for the message to count as courtesy.
COURTESY_WORDS = GREETING_WORDS | {
    "merci", "revoir", "bientot", "bye", "ok", "okay", "accord", "dac", "super", "parfait",
    "genial", "entendu", "compris", "top", "nickel", "cool", "excellent", "impeccable",
    "journee", "soiree", "continuation", "marche", "bien",
}  # fmt: skip
MAX_WORDS = 8

GREETING_REPLY = (
    "Bonjour ! Je suis l'assistant d'information d'Ynov Campus. Je peux répondre à vos "
    "questions sur les formations (BTS, Bachelors, Mastères), l'admission, les tarifs et le "
    "financement. Que souhaitez-vous savoir ?"
)
THANKS_REPLY = (
    "Avec plaisir ! N'hésitez pas si vous avez d'autres questions sur les formations Ynov, "
    "l'admission ou les tarifs."
)


def _words(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", plain)


def smalltalk_reply(text: str) -> str | None:
    """The fixed reply when `text` is only a greeting, thanks or closing, else None."""
    words = _words(text)
    if not words or len(words) > MAX_WORDS:
        return None
    if not all(w in GREETING_WORDS | THANKS_WORDS | OTHER_WORDS for w in words):
        return None
    # "et", "pour", "tres" and the like are no courtesy on their own
    if not any(w in COURTESY_WORDS for w in words):
        return None
    if any(w in GREETING_WORDS for w in words) and "merci" not in words:
        return GREETING_REPLY
    return THANKS_REPLY


def smalltalk_node(state: GraphState) -> dict:
    """Answer a greeting or thanks at once; otherwise leave the state to the next node."""
    reply = smalltalk_reply(state.get("question", ""))
    if reply is None:
        return {}
    return {"answer": reply, "sources": [], "grade": "ok", "retrieved": []}


def route_after_smalltalk(state: GraphState, default: str) -> str:
    """End when the message was answered here, else go to `default`."""
    return "end" if state.get("answer") else default
