"""Like business rules (FP-017).

Orchestrates idempotent like/unlike operations over the FP-015 storage
primitives in :mod:`social_app.likes` and reports the post's current total.
This module owns the rules only: ownership/permission checks are FP-019 and
HTTP/routes/rendering are FP-020/FP-022.

The storage primitives are imported as module globals so tests and callers can
monkeypatch them, mirroring the ``get_feed`` treatment in
:mod:`social_app.views_feed`. ``is_liked`` is re-exported here per the card's
storage contract even though this module's rules do not consult it.
"""

from social_app import db
from social_app.likes import add_like, is_liked, remove_like

__all__ = ["like", "unlike", "count_likes", "is_liked"]


def like(actor_id: int, post_id: int) -> int:
    """Idempotently like ``post_id`` as ``actor_id``; return the new total."""
    add_like(actor_id, post_id)
    return count_likes(post_id)


def unlike(actor_id: int, post_id: int) -> int:
    """Idempotently remove ``actor_id``'s like; return the new total."""
    remove_like(actor_id, post_id)
    return count_likes(post_id)


def count_likes(post_id: int) -> int:
    """Return the current number of likes on ``post_id`` (0 when none)."""
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM likes WHERE post_id = ?", (post_id,)
    )
    return row["n"]
