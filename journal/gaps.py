"""Which entries of the journal went without an answer (#20): what the visitors looked for and
did not find. Worked out when the journal is read, never stored: a better wording of the rules
below applies to the older entries too.

Kinds, one per entry, in this order of priority:
  refus       refused at the grading threshold: no passage came close to the question
  hors_ynov   the LLM declined under rule 5 of the prompt (another school, an unrelated topic)
  aveu        the LLM had a context but says it cannot answer from it
  incomplete  the LLM answers, but says that the context lacks part of what was asked
  pas_utile   any other answer the user of the chat rated "Pas utile"
Greetings (smalltalk) and errors (a technical failure, not a lack of content) have no kind.

The wordings come from the answers of the LLM saved in eval/results/ (tests/fixtures/
gap_answers.yaml). Nothing here imports the chat: chat/db.py registers `gap_kind` as an SQL
function on every connection, so that the /admin pages can filter and count with it.
"""

import re
import sqlite3

GAP_KINDS = {
    "refus": "Refus au seuil",
    "hors_ynov": "Refus hors Ynov",
    "aveu": "Le modèle ne sait pas",
    "incomplete": "Réponse incomplète",
    "pas_utile": "Jugée « Pas utile »",
}
# No answer at all; an incomplete answer or a "Pas utile" one did answer something
WITHOUT_ANSWER = ("refus", "hors_ynov", "aveu")

# "Je ne peux pas répondre (à cette question)", "je ne suis pas en mesure de répondre"
_CANNOT_ANSWER = re.compile(
    r"\bje ne (?:peux|suis) (?:donc )?pas (?:en mesure de )?(?:vous )?(?:répondre|renseigner)\b"
)
# Rule 5 of the prompt: "Je ne peux répondre qu'aux questions sur Ynov (Campus)", "je réponds
# uniquement aux questions sur Ynov", "qu'aux questions concernant les formations Ynov"
_ONLY_YNOV = re.compile(r"\b(?:qu'aux|uniquement aux|seulement aux) questions (?:\S+ ){0,4}?ynov\b")
# The verbs the LLM uses to say what the context tells, as verbs and as past participles. Not
# "spécifique" ("ce module n'est pas spécifique au M2" says nothing about the context).
_TELLS = r"(?:contien|précis|mentionn|indiqu|détaill|cit|spécifi|fourni|list)\w*"
_TOLD = r"(?:précisé|mentionné|indiqué|détaillé|cité|spécifié|listé|fourni)e?s?\b"
_GAP_PHRASES = [
    # "le contexte ne précise pas", "les pages ne précisent pas explicitement", "il ne contient pas"
    rf"\bne {_TELLS} (?:explicitement |clairement )?pas\b",
    # "ne sont pas mentionnées dans le contexte", "n'est pas explicitement précisé"
    rf"\b(?:n'est|ne sont) pas (?:\S+ )?{_TOLD}",
    r"\b(?:n'est|ne sont) pas disponibles? dans (?:le|les|ce|ces) (?:contexte|sources?|extraits?)",
    # "aucun passage ne mentionne", "aucun autre module spécifique au mastère 2 n'est mentionné"
    rf"\baucune? (?:\S+ ){{0,8}}?ne {_TELLS}",
    rf"\baucune? (?:\S+ ){{0,8}}?(?:n'est|ne sont|n'a été|n'ont été) (?:\S+ )?{_TOLD}",
    r"\baucune information\b",
    r"\bpas d'informations?\b",
    r"\bje ne dispose (?:d'aucune|pas)\b",
    r"\bsans (?:le |la |les )?(?:préciser|mentionner|indiquer|détailler)\b",
]
_GAP = re.compile("|".join(_GAP_PHRASES))
# Sentences that only talk about the sources or send the reader elsewhere: they neither answer
# nor report a gap. "Les informations disponibles concernent uniquement…", "Pour une liste
# complète, il faudrait consulter la fiche RNCP", "Je suis désolé."
_ASIDE = re.compile(
    r"^(?:les|ces) (?:informations|sources|extraits|documents|passages)\b[^.]{0,30}"
    r"\b(?:concernent|portent|traitent)\b"
    r"|\b(?:il faudrait|il est (?:recommandé|conseillé) de|je vous (?:invite|conseille|recommande)"
    r"|n'hésitez pas|vous pouvez (?:contacter|consulter)|contactez|consultez)\b"
    r"|^je suis désolée?\W*$"
)
_SOURCE_MARK = re.compile(r"\[sources?[^\]]*\]")
_SENTENCE_END = re.compile(r"(?<=[.!?:])\s+|\n+")
_MIN_WORDS = 3  # shorter pieces ("Par exemple :", "[Source 2]") are not sentences


def _plain(text: str) -> str:
    """Lower case, straight apostrophes, no Markdown emphasis, single spaces."""
    text = text.lower().replace("’", "'").replace("‘", "'").replace(" ", " ")
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"[ \t]+", " ", text)


def _sentences(text: str) -> list[str]:
    pieces = (_SOURCE_MARK.sub("", piece).strip(" -–—()•") for piece in _SENTENCE_END.split(text))
    return [p for p in pieces if len(p.split()) >= _MIN_WORDS]


def answer_gap(answer: str) -> str | None:
    """What a generated answer says about the context: "hors_ynov", "aveu", "incomplete", or
    None for an answer that does not report anything missing."""
    text = _plain(answer or "")
    if _ONLY_YNOV.search(text):
        return "hors_ynov"
    if _CANNOT_ANSWER.search(text):
        return "aveu"
    gaps = facts = 0
    for sentence in _sentences(text):
        if _GAP.search(sentence):
            gaps += 1
        elif not _ASIDE.search(sentence):
            facts += 1
    if not gaps:
        return None
    # Nothing but what is missing (and asides): the answer gives nothing else
    return "incomplete" if facts else "aveu"


def gap_kind(route: str | None, answer: str | None, feedback: int | None) -> str | None:
    """The kind of the entry (see GAP_KINDS), or None when it got an answer."""
    if route == "refuse":
        return "refus"
    if route != "generate":  # greetings and errors
        return None
    return answer_gap(answer or "") or ("pas_utile" if feedback == 0 else None)


def register(conn: sqlite3.Connection) -> None:
    """Make gap_kind(route, answer, feedback) usable in the SQL of this connection."""
    conn.create_function("gap_kind", 3, gap_kind, deterministic=True)
