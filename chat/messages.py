"""Pure helpers of the chat: the sources block of an answer and the history of a thread."""
import re

# Author of the assistant messages: its avatar is requested as /avatars/<author>, and Chainlit
# only accepts letters, digits, spaces, "_", "." and "-" there (the app name has parentheses).
# Without a file in chat/public/avatars it falls back to the favicon.
AUTHOR = "Chatbot Ynov"
SOURCES_HEADING = "**Sources**"
_SOURCES_SEPARATOR = f"\n\n{SOURCES_HEADING}\n"


def cited_numbers(answer: str) -> list[int]:
    """Numbers of the sources the answer cites ("[Source 3, Source 7]" -> [3, 7])."""
    return sorted({int(n) for n in re.findall(r"Source (\d+)", answer)})


def with_sources(answer: str, sources: list[dict]) -> str:
    """The answer followed by the list of the sources it cites, numbered like in the text."""
    lines = []
    for number in cited_numbers(answer):
        if not 1 <= number <= len(sources):
            continue
        src = sources[number - 1]
        label = src["source"]
        if src.get("section"):
            label += f" — {src['section']}"
        if src.get("page") and not src["source"].endswith(".html"):  # HTML pages have no pages
            label += f" (p. {src['page']})"
        lines.append(f"{number}. {label}")
    if not lines:
        return answer
    return answer + _SOURCES_SEPARATOR + "\n".join(lines)


def strip_sources(text: str) -> str:
    """The answer without its sources block: that is what the LLM gets as history."""
    return text.split(_SOURCES_SEPARATOR, 1)[0]


def history_from_steps(steps: list[dict], skip: str | None = None) -> list[dict]:
    """Rebuild the chat history of a resumed thread from its persisted steps.

    `skip` is the greeting, an assistant message that is not part of the conversation.
    """
    roles = {"user_message": "user", "assistant_message": "assistant"}
    history = []
    for step in steps:
        role = roles.get(step.get("type", ""))
        content = (step.get("output") or "").strip()
        if role is None or not content or content == skip:
            continue
        history.append({"role": role, "content": strip_sources(content) if role == "assistant"
                        else content})
    return history
