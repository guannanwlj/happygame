"""Authentication & session contract slice (FP-003, not yet merged).

Task card FP-010 §3.2 / §6: until FP-003 lands, this module provides the
minimal contract the posts feature calls into. Login state lives in the
session under ``user_id`` (tests inject it via ``session_transaction``);
FP-003's real implementation replaces this file at integration point I-22.
"""

from functools import wraps
from urllib.parse import quote

from flask import redirect, request, session


def current_user_id() -> int | None:
    """Return the logged-in user's id, or None for an anonymous session."""
    user_id = session.get("user_id")
    return user_id if isinstance(user_id, int) else None


def login_required(view):
    """Reject anonymous access with 302 to /login?next=<request.path>."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect(f"/login?next={quote(request.path)}")
        return view(*args, **kwargs)

    return wrapped
