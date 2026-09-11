"""Like relationships between users and comments (FP-001).

Thin storage layer over the generic API in :mod:`social_app.db`. A comment like
is stored as one ``(user_id, comment_id)`` row, independent of the post ``likes``
table. This module provides storage primitives only: idempotency is guaranteed by
the ``UNIQUE (user_id, comment_id)`` constraint plus ``INSERT OR IGNORE``.
Business rules (count orchestration, authorization, routes) live in
FP-003/FP-004/FP-006.
"""

from social_app import db


def add_comment_like(user_id: int, comment_id: int) -> bool:
    """Idempotently record that ``user_id`` likes ``comment_id``.

    Returns ``True`` when a new row was inserted, ``False`` when the like
    already existed. Duplicate likes are ignored rather than raising.
    """
    cur = db.execute(
        "INSERT OR IGNORE INTO comment_likes (user_id, comment_id) VALUES (?, ?)",
        (user_id, comment_id),
    )
    return cur.rowcount == 1


def remove_comment_like(user_id: int, comment_id: int) -> bool:
    """Idempotently delete the like of ``comment_id`` by ``user_id``.

    Returns ``True`` when a row was deleted, ``False`` when no such like
    existed. Removing a missing like is not an error.
    """
    cur = db.execute(
        "DELETE FROM comment_likes WHERE user_id = ? AND comment_id = ?",
        (user_id, comment_id),
    )
    return cur.rowcount == 1


def is_comment_liked(user_id: int, comment_id: int) -> bool:
    """Return ``True`` iff ``user_id`` currently likes ``comment_id``."""
    row = db.query_one(
        "SELECT 1 FROM comment_likes WHERE user_id = ? AND comment_id = ? LIMIT 1",
        (user_id, comment_id),
    )
    return row is not None


def count_comment_likes(comment_id: int) -> int:
    """Return the number of likes on ``comment_id`` (0 when none)."""
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM comment_likes WHERE comment_id = ?",
        (comment_id,),
    )
    return int(row["n"])
