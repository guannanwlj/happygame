"""Auth contract slice for FP-011 (self-built per task card §3.2/§6).

FP-003 owns the real implementation; until it merges, this module provides
exactly the contract the feed needs: login state lives in the Flask session
under ``user_id`` (tests inject it with ``session_transaction``), and
``login_required`` bounces anonymous requests to the login page. Swapped at
integration point I-23.
"""

from functools import wraps

from flask import redirect, session

USER_ID_SESSION_KEY = "user_id"
LOGIN_URL = "/login"


def current_user_id() -> int | None:
    """Return the logged-in user's id from the session, or None."""
    return session.get(USER_ID_SESSION_KEY)


def login_required(view):
    """Reject anonymous requests with a 302 to the login page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect(LOGIN_URL)
        return view(*args, **kwargs)

    return wrapped
