"""One-directional follow relationships (FP-004).

Thin wrapper over the generic storage API in :mod:`social_app.db`. A follow is
stored as a single ``(follower_id, followee_id)`` row; following is never
symmetric. Validation rules (self-follow, target existence, login) live in
FP-011 — this module only performs storage operations.
"""

from social_app import db


def add_follow(follower_id: int, followee_id: int) -> bool:
    """Idempotently record that ``follower_id`` follows ``followee_id``.

    Returns ``True`` when a new row was inserted, ``False`` when the follow
    already existed. Duplicate follows are ignored rather than raising.
    """
    cur = db.execute(
        "INSERT OR IGNORE INTO follows (follower_id, followee_id) VALUES (?, ?)",
        (follower_id, followee_id),
    )
    return cur.rowcount == 1


def is_following(follower_id: int, followee_id: int) -> bool:
    """Return ``True`` iff ``follower_id`` follows ``followee_id``."""
    row = db.query_one(
        "SELECT 1 FROM follows WHERE follower_id = ? AND followee_id = ? LIMIT 1",
        (follower_id, followee_id),
    )
    return row is not None


def list_followees(follower_id: int) -> list[int]:
    """Return the ids that ``follower_id`` follows, in insertion order."""
    rows = db.query_all(
        "SELECT followee_id FROM follows WHERE follower_id = ? ORDER BY id",
        (follower_id,),
    )
    return [row["followee_id"] for row in rows]
