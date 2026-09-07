"""Authentication & session helpers (FP-005 stand-in for the FP-003 contract).

FP-003's real module is not merged yet, so this file implements the card
FP-005 §3.2 contract slice with an inline stdlib PBKDF2 implementation.
Integration point I-07 replaces this with FP-003's real module; the function
signatures must stay identical:

    hash_password(plain) -> str
    verify_password(plain, stored) -> bool
    login_user(user_id) -> None        # session['user_id'] = user_id
    logout_user() -> None              # session.clear()
    current_user_id() -> int | None
    login_required(view)               # anonymous -> 302 /login?next=<path>
"""

import base64
import functools
import hashlib
import hmac
import os

from flask import redirect, request, session, url_for

_ALGORITHM = "sha256"
_ITERATIONS = 60_000
_SALT_BYTES = 16
_PREFIX = f"pbkdf2_{_ALGORITHM}"


def hash_password(plain: str) -> str:
    """Hash a plaintext password with PBKDF2-HMAC-SHA256 and a random salt.

    Stored format: ``pbkdf2_sha256$<iterations>$<salt-b64>$<digest-b64>`` so
    the parameter set travels with each stored hash.
    """
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_ALGORITHM, plain.encode(), salt, _ITERATIONS)
    return "$".join(
        (
            _PREFIX,
            str(_ITERATIONS),
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        )
    )


def verify_password(plain: str, stored: str) -> bool:
    """Check a plaintext password against a stored hash.

    Fail-closed: any malformed stored value (wrong tag, bad numbers, bad
    base64) yields ``False`` instead of raising, so corrupted rows degrade to
    "wrong credentials" rather than a server error.
    """
    parts = stored.split("$") if isinstance(stored, str) else []
    if len(parts) != 4 or parts[0] != _PREFIX:
        return False
    try:
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2], validate=True)
        expected = base64.b64decode(parts[3], validate=True)
    except (ValueError, TypeError):
        return False
    if iterations <= 0:
        return False
    candidate = hashlib.pbkdf2_hmac(_ALGORITHM, plain.encode(), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def login_user(user_id: int) -> None:
    """Establish the login state for this session."""
    session["user_id"] = user_id


def logout_user() -> None:
    """Destroy the session (any other session data goes with it)."""
    session.clear()


def current_user_id() -> int | None:
    """Return the logged-in user's id, or None for an anonymous session."""
    return session.get("user_id")


def login_required(view):
    """Reject anonymous requests with 302 /login?next=<path>."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect(url_for("login.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped
