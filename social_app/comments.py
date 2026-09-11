"""Comment persistence (FP-016).

Thin storage wrapper over the generic API in :mod:`social_app.db`. A comment
records who wrote what on which post and when. This module only reads and
writes rows: content non-emptiness rules, readable errors and other business
rules belong to FP-018, ownership checks to FP-019, and HTTP handling to
FP-021/FP-022.
"""

import sqlite3

from social_app import db


def add_comment(post_id: int, author_id: int, content: str) -> int:
    """Store a comment and return its newly assigned id.

    ``created_at`` is filled by the schema default. Foreign keys on
    ``post_id``/``author_id`` are enforced, so referencing a missing post or
    user raises :class:`sqlite3.IntegrityError`.
    """
    cur = db.execute(
        "INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
        (post_id, author_id, content),
    )
    return cur.lastrowid


def list_comments(post_id: int) -> list[sqlite3.Row]:
    """Return a post's comments oldest first, tie-broken by ascending id."""
    return db.query_all(
        "SELECT id, post_id, author_id, content, created_at FROM comments"
        " WHERE post_id = ? ORDER BY created_at ASC, id ASC",
        (post_id,),
    )
