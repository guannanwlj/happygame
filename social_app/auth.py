"""Authentication & session management (FP-003).

Implements the auth contract of task card FP-003 §3.2: salted PBKDF2
password hashing/verification, Flask signed-cookie session helpers, and the
``login_required`` gate for protected views. Credentials live in the FP-001
``users`` table; plaintext passwords are never stored (D-004). This module is
the single enforcement point reused by later feature tasks (FP-004/005/…).
"""

import functools
import hashlib
import hmac
import secrets
from urllib.parse import quote

from flask import redirect, request, session

HASH_METHOD = "pbkdf2:sha256"
PBKDF2_ITERATIONS = 600_000
MAX_PBKDF2_ITERATIONS = 1_000_000
SALT_BYTES = 16
SESSION_USER_ID_KEY = "user_id"


def hash_password(plain: str) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash of ``plain``.

    Self-contained format (card §3.2):
    ``pbkdf2:sha256$<iterations>$<salt_hex>$<hash_hex>`` — semantically
    equivalent to werkzeug's ``pbkdf2:sha256`` method.
    """
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"{HASH_METHOD}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """Check ``plain`` against ``stored``; ``False`` for any malformed input.

    Recomputes the digest with the parameters embedded in ``stored`` and
    compares in constant time. Untrusted strings are parsed strictly (method
    allowlist, iteration cap) so a hostile stored hash cannot trigger KDF work.
    """
    try:
        method, iterations_text, salt_hex, digest_hex = stored.split("$")
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        if method != HASH_METHOD or not 0 < iterations <= MAX_PBKDF2_ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), salt, iterations
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def login_user(user_id: int) -> None:
    """Establish the login session: ``session['user_id'] = user_id``."""
    session[SESSION_USER_ID_KEY] = user_id


def logout_user() -> None:
    """Destroy the session entirely."""
    session.clear()


def current_user_id() -> int | None:
    """Return the logged-in user id, or ``None`` when anonymous."""
    return session.get(SESSION_USER_ID_KEY)


def login_required(view):
    """Gate a view: anonymous callers get 302 ``/login?next=<request.path>``."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect("/login?next=" + quote(request.path))
        return view(*args, **kwargs)

    return wrapped
