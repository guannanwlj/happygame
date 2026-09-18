"""Session primitives & unified ``login_required`` guard (FP-003).

Login state lives entirely in Flask's signed-cookie session under
``session["user_id"]`` — the single source of the session contract that
FP-005..FP-013 consume:

- ``login_user(user_id)`` — establish (or overwrite) a login session;
- ``logout_user()`` — destroy the session (``session.clear()``);
- ``current_user_id()`` — read the logged-in user id, ``None`` when signed out;
- ``login_required(view)`` — 302-redirect unauthenticated requests to the
  literal path ``"/login"`` (never reverse-looked-up, so this module carries
  no dependency on the login-page task).

No database access happens here: deciding login state only reads the session.
"""

from collections.abc import Callable
from functools import wraps

from flask import redirect, session

LOGIN_URL = "/login"


def login_user(user_id: int) -> None:
    """Establish a login session for ``user_id``.

    Assignment overwrites any previous value, so a new login invalidates the
    old session by construction.
    """
    session["user_id"] = user_id


def logout_user() -> None:
    """Destroy the login session (clears every session key)."""
    session.clear()


def current_user_id() -> int | None:
    """Return the logged-in user id, or ``None`` when signed out."""
    return session.get("user_id")


def login_required(view: Callable) -> Callable:
    """Require a logged-in session for ``view``; otherwise 302 to ``/login``."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect(LOGIN_URL)
        return view(*args, **kwargs)

    return wrapped
