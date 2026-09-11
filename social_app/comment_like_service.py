"""Comment like business rules (FP-006).

Orchestrates idempotent like/unlike operations over the FP-001 storage
primitives in :mod:`social_app.comment_likes` and reports the comment's current
total. This module owns the rules only: authorization is FP-003 and
HTTP/routes/rendering are FP-004/FP-005.

The storage primitives are imported as module globals so tests and callers can
monkeypatch them, mirroring :mod:`social_app.like_service`.
"""

from social_app.comment_likes import (
    add_comment_like,
    count_comment_likes,
    remove_comment_like,
)

__all__ = ["like_comment", "unlike_comment", "count_comment_likes"]


def like_comment(actor_id: int, comment_id: int) -> int:
    """Idempotently like ``comment_id`` as ``actor_id``; return the new total.

    Self-likes are allowed (D6); no ownership check is performed here.
    """
    add_comment_like(actor_id, comment_id)
    return count_comment_likes(comment_id)


def unlike_comment(actor_id: int, comment_id: int) -> int:
    """Idempotently remove ``actor_id``'s like; return the new total."""
    remove_comment_like(actor_id, comment_id)
    return count_comment_likes(comment_id)
