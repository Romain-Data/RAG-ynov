"""Accounts: a pseudo and a password, nothing else (no e-mail, no name, no IP).

A recovery code is shown once at sign-up (and again after each recovery): it is the only
way to reset a forgotten password, since there is no e-mail to write to. Only argon2
hashes are stored. AccountError messages are in French and safe to show to the user.
"""
import re
import secrets
import sqlite3
import time
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from chat.db import db

PSEUDO_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD, MAX_PASSWORD = 8, 128
# Failed attempts per pseudo (memory only, so no IP is kept): 5 in 5 minutes, then wait.
MAX_FAILURES, WINDOW_S = 5, 300
# No ambiguous characters (0/O, 1/I): the code is copied by hand
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("not-a-real-password")  # verified when the pseudo is unknown
_failures: dict[str, list[float]] = {}


class AccountError(ValueError):
    """An error to show to the user as is."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _throttled(pseudo: str) -> bool:
    cutoff = time.monotonic() - WINDOW_S
    recent = [t for t in _failures.get(pseudo.lower(), []) if t > cutoff]
    return len(recent) >= MAX_FAILURES


def _record_failure(pseudo: str) -> None:
    now = time.monotonic()
    if len(_failures) > 1000:  # pseudos typed by a stranger must not pile up
        for key in [k for k, v in _failures.items() if not v or v[-1] < now - WINDOW_S]:
            del _failures[key]
    _failures.setdefault(pseudo.lower(), []).append(now)


def _check_throttle(pseudo: str) -> None:
    if _throttled(pseudo):
        raise AccountError("Trop de tentatives. Réessayez dans quelques minutes.")


def _new_code() -> str:
    chars = [secrets.choice(_CODE_ALPHABET) for _ in range(16)]
    return "-".join("".join(chars[i:i + 4]) for i in range(0, 16, 4))


def _normalize_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code).upper()


def _hash_code(code: str) -> str:
    return _hasher.hash(_normalize_code(code))


def check_password_rules(password: str) -> None:
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise AccountError(
            f"Le mot de passe doit faire entre {MIN_PASSWORD} et {MAX_PASSWORD} caractères."
        )


def register(pseudo: str, password: str) -> str:
    """Create an account and return its recovery code (shown once)."""
    pseudo = pseudo.strip()
    if not PSEUDO_RE.match(pseudo):
        raise AccountError(
            "Le pseudo doit faire de 3 à 30 caractères : lettres, chiffres, point, tiret ou "
            "tiret bas."
        )
    check_password_rules(password)
    code = _new_code()
    with db() as conn:
        taken = conn.execute("SELECT 1 FROM accounts WHERE pseudo = ?", (pseudo,)).fetchone()
        if taken:
            raise AccountError("Ce pseudo est déjà pris.")
        try:
            conn.execute(
                "INSERT INTO accounts (pseudo, password_hash, recovery_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (pseudo, _hasher.hash(password), _hash_code(code), _now()),
            )
        except sqlite3.IntegrityError:  # the same pseudo was created in between
            raise AccountError("Ce pseudo est déjà pris.") from None
    return code


def _verify(hash_: str, secret: str) -> bool:
    try:
        return _hasher.verify(hash_, secret)
    except (VerifyMismatchError, InvalidHashError):
        return False


def authenticate(pseudo: str, password: str) -> str | None:
    """The pseudo as stored (its case is the one chosen at sign-up) if the password is
    right, else None. Also None while the pseudo is throttled."""
    pseudo = pseudo.strip()
    if _throttled(pseudo):
        return None
    with db() as conn:
        row = conn.execute(
            "SELECT pseudo, password_hash FROM accounts WHERE pseudo = ?", (pseudo,)
        ).fetchone()
        # An unknown pseudo costs the same time as a wrong password
        if _verify(row[1] if row else _DUMMY_HASH, password) and row:
            conn.execute(
                "UPDATE accounts SET last_login_at = ? WHERE pseudo = ?", (_now(), row[0])
            )
            return str(row[0])
    _record_failure(pseudo)
    return None


def recover(pseudo: str, code: str, new_password: str) -> str:
    """Set a new password with the recovery code; returns the new recovery code."""
    pseudo = pseudo.strip()
    _check_throttle(pseudo)
    check_password_rules(new_password)
    new_code = _new_code()
    with db() as conn:
        row = conn.execute(
            "SELECT pseudo, recovery_hash FROM accounts WHERE pseudo = ?", (pseudo,)
        ).fetchone()
        if not (_verify(row[1] if row else _DUMMY_HASH, _normalize_code(code)) and row):
            _record_failure(pseudo)
            raise AccountError("Pseudo ou code de secours incorrect.")
        conn.execute(
            "UPDATE accounts SET password_hash = ?, recovery_hash = ? WHERE pseudo = ?",
            (_hasher.hash(new_password), _hash_code(new_code), row[0]),
        )
    return new_code


def delete_account(pseudo: str, password: str) -> None:
    """Delete the account and everything it owns: conversations, messages, feedback."""
    pseudo = pseudo.strip()
    _check_throttle(pseudo)
    account = authenticate(pseudo, password)
    if account is None:
        raise AccountError("Pseudo ou mot de passe incorrect.")
    with db() as conn:
        threads = "SELECT id FROM threads WHERE userIdentifier = ?"
        for table, column in (("steps", "threadId"), ("elements", "threadId"),
                              ("feedbacks", "threadId")):
            conn.execute(f"DELETE FROM {table} WHERE {column} IN ({threads})", (account,))
        conn.execute("DELETE FROM threads WHERE userIdentifier = ?", (account,))
        conn.execute("DELETE FROM users WHERE identifier = ?", (account,))
        conn.execute("DELETE FROM accounts WHERE pseudo = ?", (account,))
