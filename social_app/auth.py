"""Authentication session contract slice consumed by FP-006 (task card §3.2).

Implements only the pieces of the FP-003 contract that FP-006 calls:
``current_user_id`` and the ``login_required`` interceptor (unauthenticated
request -> 302 ``/login?next=<request.path>``). The full module (password
hashing, login/logout session helpers) lands with FP-003 and replaces this
slice wholesale (integration point I-11); import sites stay unchanged.
"""

import functools
from urllib.parse import quote

from flask import redirect, request, session


def current_user_id() -> int | None:
    """Return the logged-in user's id, or None when unauthenticated."""
    return session.get("user_id")


def login_required(view):
    """Reject unauthenticated requests with a redirect to the login page."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect(f"/login?next={quote(request.path)}")
        return view(*args, **kwargs)

    return wrapped
