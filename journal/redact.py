"""Mask the e-mail addresses and phone numbers a user may type in a question."""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 9 to 14 digits, possibly separated by spaces, dots or dashes, with an optional +/00 prefix
# (French numbers: 06 12 34 56 78, +33 6 12 34 56 78)
_PHONE = re.compile(r"(?<![\w+])(?:\+|00)?\d(?:[ .-]?\d){8,13}(?!\d)")


def redact(text: str) -> str:
    return _PHONE.sub("[téléphone]", _EMAIL.sub("[e-mail]", text))
