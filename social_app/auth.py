"""Authentication & session domain logic (FP-003).

Business rules on top of the FP-001 storage module: password hashing, input
validation, registration, credential checking, and cookie-session helpers.
No Flask imports here — the HTTP layer lives in social_app.routes.
"""

import re
import sqlite3
from collections.abc import MutableMapping
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from social_app import db

USERNAME_MIN = 3
USERNAME_MAX = 32
PASSWORD_MIN = 8
PASSWORD_MAX = 128
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]+")

SESSION_USER_ID_KEY = "user_id"


class AuthError(Exception):
    """Base class for all authentication domain errors."""


class ValidationError(AuthError):
    """Input failed a validation rule (username/password shape)."""


class UsernameTakenError(AuthError):
    """Registration attempted with an already existing username."""


class InvalidCredentialsError(AuthError):
    """Login failed (unknown user or wrong password)."""


def hash_password(password: str) -> str:
    """Return a salted hash for the password (plaintext never stored)."""
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Check a plaintext password against a stored hash."""
    return check_password_hash(password_hash, password)


def validate_username(username: Any) -> None:
    """Raise ValidationError unless username matches the documented rules."""
    if not isinstance(username, str):
        raise ValidationError("username must be a string")
    if not USERNAME_MIN <= len(username) <= USERNAME_MAX:
        raise ValidationError(
            f"username must be {USERNAME_MIN}-{USERNAME_MAX} characters long"
        )
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValidationError(
            "username may only contain letters, digits and underscore"
        )


def validate_password(password: Any) -> None:
    """Raise ValidationError unless password matches the documented rules."""
    if not isinstance(password, str):
        raise ValidationError("password must be a string")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise ValidationError(
            f"password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters long"
        )


def register_user(username: Any, password: Any) -> sqlite3.Row:
    """Create a user with a hashed password; return the stored row.

    Raises ValidationError for bad input and UsernameTakenError on duplicates.
    """
    validate_username(username)
    validate_password(password)
    try:
        cur = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
    except sqlite3.IntegrityError as exc:
        raise UsernameTakenError(f"username {username!r} is already taken") from exc
    row = db.query_one("SELECT * FROM users WHERE id = ?", (cur.lastrowid,))
    assert row is not None, "inserted row must be readable"
    return row


def authenticate(username: Any, password: Any) -> sqlite3.Row:
    """Return the user row when credentials match, else raise.

    Unknown username and wrong password raise the same InvalidCredentialsError
    so callers cannot enumerate registered usernames.
    """
    row = db.query_one("SELECT * FROM users WHERE username = ?", (username,))
    if (
        row is None
        or not isinstance(password, str)
        or not verify_password(row["password_hash"], password)
    ):
        raise InvalidCredentialsError("invalid username or password")
    return row


def get_user(user_id: int) -> sqlite3.Row | None:
    """Return the user row for the id, or None if it does not exist."""
    return db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def login_session(session: MutableMapping[str, Any], user_id: int) -> None:
    """Start an authenticated session, discarding any prior content."""
    session.clear()
    session[SESSION_USER_ID_KEY] = user_id


def logout_session(session: MutableMapping[str, Any]) -> None:
    """End the session (idempotent)."""
    session.clear()


def session_user_id(session: MutableMapping[str, Any]) -> int | None:
    """Return the logged-in user id, or None for an anonymous session."""
    return session.get(SESSION_USER_ID_KEY)


def current_user(session: MutableMapping[str, Any]) -> sqlite3.Row | None:
    """Resolve the session to a live user row; None when anonymous/deleted."""
    user_id = session_user_id(session)
    if user_id is None:
        return None
    return get_user(user_id)
