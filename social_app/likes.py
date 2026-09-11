"""Like relationships between users and posts (FP-015).

Thin storage layer over the generic API in :mod:`social_app.db`. A like is
stored as one ``(user_id, post_id)`` row. This module provides storage
primitives only: idempotency is guaranteed by the ``UNIQUE (user_id, post_id)``
constraint plus ``INSERT OR IGNORE``. Business rules (like/unlike orchestration,
total counts, ownership and login checks) live in FP-017/FP-019/FP-020.
"""

from social_app import db


def add_like(user_id: int, post_id: int) -> bool:
    """Idempotently record that ``user_id`` likes ``post_id``.

    Returns ``True`` when a new row was inserted, ``False`` when the like
    already existed. Duplicate likes are ignored rather than raising.
    """
    cur = db.execute(
        "INSERT OR IGNORE INTO likes (user_id, post_id) VALUES (?, ?)",
        (user_id, post_id),
    )
    return cur.rowcount == 1


def remove_like(user_id: int, post_id: int) -> bool:
    """Idempotently delete the like of ``post_id`` by ``user_id``.

    Returns ``True`` when a row was deleted, ``False`` when no such like
    existed. Removing a missing like is not an error.
    """
    cur = db.execute(
        "DELETE FROM likes WHERE user_id = ? AND post_id = ?",
        (user_id, post_id),
    )
    return cur.rowcount == 1


def is_liked(user_id: int, post_id: int) -> bool:
    """Return ``True`` iff ``user_id`` currently likes ``post_id``."""
    row = db.query_one(
        "SELECT 1 FROM likes WHERE user_id = ? AND post_id = ? LIMIT 1",
        (user_id, post_id),
    )
    return row is not None
