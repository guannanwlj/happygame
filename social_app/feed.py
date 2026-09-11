"""Feed query module (FP-023).

Read-only aggregation for the home feed: the posts authored by ``user_id`` or
by anyone ``user_id`` follows, newest first, each annotated with its total like
count, whether the viewer liked it, and its comments in ascending order.

All access goes through the generic storage API in :mod:`social_app.db`; the
existing ``posts`` / ``follows`` / ``users`` tables are read directly, as are
the FP-015 ``likes`` and FP-016 ``comments`` tables. Writing posts, likes or
comments, HTML rendering and pagination are out of scope (card §5).
"""

from social_app import db
from social_app.follows import list_followees


def _like_count(post_id: int) -> int:
    """Return the total number of likes recorded for ``post_id``."""
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM likes WHERE post_id = ?", (post_id,)
    )
    return int(row["n"])


def _liked_by_me(user_id: int, post_id: int) -> bool:
    """Return ``True`` iff ``user_id`` currently likes ``post_id``."""
    row = db.query_one(
        "SELECT 1 FROM likes WHERE user_id = ? AND post_id = ? LIMIT 1",
        (user_id, post_id),
    )
    return row is not None


def _comments(post_id: int) -> list[dict]:
    """Return ``post_id``'s comments in ascending time order with usernames."""
    rows = db.query_all(
        "SELECT u.username AS author, c.content, c.created_at "
        "FROM comments c JOIN users u ON u.id = c.author_id "
        "WHERE c.post_id = ? ORDER BY c.created_at ASC, c.id ASC",
        (post_id,),
    )
    return [
        {
            "author": row["author"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_feed(user_id: int) -> list[dict]:
    """Return self + followees' posts, newest first, with interaction data.

    Each row is a dict with keys ``post_id``, ``author_id``, ``username``,
    ``content``, ``created_at``, ``like_count``, ``liked_by_me`` and
    ``comments`` (a list of ``{author, content, created_at}``, ascending).
    Posts are ordered ``created_at DESC, id DESC``. Returns ``[]`` when the
    user follows no one and has no posts.
    """
    author_ids = list_followees(user_id)
    author_ids.append(user_id)
    placeholders = ",".join("?" for _ in author_ids)
    rows = db.query_all(
        "SELECT p.id, p.author_id, u.username, p.content, p.created_at "
        "FROM posts p JOIN users u ON u.id = p.author_id "
        f"WHERE p.author_id IN ({placeholders}) "
        "ORDER BY p.created_at DESC, p.id DESC",
        tuple(author_ids),
    )
    return [
        {
            "post_id": row["id"],
            "author_id": row["author_id"],
            "username": row["username"],
            "content": row["content"],
            "created_at": row["created_at"],
            "like_count": _like_count(row["id"]),
            "liked_by_me": _liked_by_me(user_id, row["id"]),
            "comments": _comments(row["id"]),
        }
        for row in rows
    ]
