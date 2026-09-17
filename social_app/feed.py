"""Feed query module (FP-023, extended by FP-009 and FP-003).

Read-only aggregation for the home feed: the posts authored by ``user_id`` or
by anyone ``user_id`` follows, newest first, each annotated with its total like
count, whether the viewer liked it, and its comments in ascending order.

FP-009 extends ``_comments`` so every comment also carries its reply relation
(``parent_id``) and comment-like data (``like_count`` / ``liked_by_me``, viewer
specific). Both are read from the FP-001/FP-002 tables when present and degrade
to defaults otherwise (weak dependencies).

FP-003 makes ``_comments`` the comment-visibility convergence point: the raw
rows (now including ``c.author_id``) pass through
:func:`social_app.comment_visibility.visible_comments` before the FP-009 dicts
are assembled, so mutual-friend posts only show comments from their visible
set while own / non-mutual posts keep the status quo. Filtering is a pure
subset selection — order and dict shape are unchanged.

All access goes through the generic storage API in :mod:`social_app.db`; the
existing ``posts`` / ``follows`` / ``users`` tables are read directly, as are
the FP-015 ``likes``, FP-016 ``comments`` and FP-001 ``comment_likes`` tables.
Writing posts, likes, comments or replies, HTML rendering and pagination are out
of scope (card §5).
"""

from social_app import db
from social_app.comment_visibility import visible_comments
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


def _has_parent_id() -> bool:
    """Return ``True`` iff FP-002 added ``comments.parent_id`` (weak dep)."""
    columns = db.query_all("PRAGMA table_info(comments)")
    return any(row["name"] == "parent_id" for row in columns)


def _has_comment_likes() -> bool:
    """Return ``True`` iff FP-001's ``comment_likes`` table exists (weak dep)."""
    row = db.query_one(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'comment_likes'"
    )
    return row is not None


def _post_author_id(post_id: int) -> int | None:
    """Return the author of ``post_id`` (None if the post row is gone)."""
    row = db.query_one("SELECT author_id FROM posts WHERE id = ?", (post_id,))
    return None if row is None else row["author_id"]


def _comments(
    post_id: int, viewer_id: int, post_author_id: int | None = None
) -> list[dict]:
    """Return ``post_id``'s visible comments (and replies) in ascending order.

    Each dict carries the FP-009 contract (card §3.2): ``comment_id``,
    ``parent_id``, ``author``, ``content``, ``created_at``, ``like_count`` and
    ``liked_by_me`` (viewer specific). Rows are ordered ``created_at ASC,
    id ASC``.

    FP-003 filters the raw rows (which select ``c.author_id``) through
    ``visible_comments(post_author_id, viewer_id, ...)`` before the dicts are
    assembled. ``post_author_id`` defaults to a single lookup so legacy
    two-argument callers still get full filtering semantics (card §3.2).

    FP-001/FP-002 are weak dependencies (``comment_likes`` table and
    ``comments.parent_id``). While both are missing the query degrades to the
    legacy ``{author, content, created_at}`` shape so the FP-023 contract keeps
    passing (card §6).
    """
    if post_author_id is None:
        post_author_id = _post_author_id(post_id)
    has_parent = _has_parent_id()
    has_likes = _has_comment_likes()
    if not has_parent and not has_likes:
        rows = db.query_all(
            "SELECT c.author_id, u.username AS author, c.content, c.created_at "
            "FROM comments c JOIN users u ON u.id = c.author_id "
            "WHERE c.post_id = ? ORDER BY c.created_at ASC, c.id ASC",
            (post_id,),
        )
        rows = visible_comments(post_author_id, viewer_id, rows)
        return [
            {
                "author": row["author"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    parent_col = "c.parent_id" if has_parent else "NULL"
    if has_likes:
        like_count = "(SELECT COUNT(*) FROM comment_likes cl WHERE cl.comment_id = c.id)"
        liked_by_me = (
            "EXISTS(SELECT 1 FROM comment_likes cl "
            "WHERE cl.comment_id = c.id AND cl.user_id = ?)"
        )
        params: tuple = (viewer_id, post_id)
    else:
        like_count = "0"
        liked_by_me = "0"
        params = (post_id,)

    rows = db.query_all(
        f"SELECT c.id AS comment_id, {parent_col} AS parent_id, "
        "c.author_id, u.username AS author, c.content, c.created_at, "
        f"{like_count} AS like_count, {liked_by_me} AS liked_by_me "
        "FROM comments c JOIN users u ON u.id = c.author_id "
        "WHERE c.post_id = ? ORDER BY c.created_at ASC, c.id ASC",
        params,
    )
    rows = visible_comments(post_author_id, viewer_id, rows)
    return [
        {
            "comment_id": row["comment_id"],
            "parent_id": row["parent_id"],
            "author": row["author"],
            "content": row["content"],
            "created_at": row["created_at"],
            "like_count": int(row["like_count"]),
            "liked_by_me": bool(row["liked_by_me"]),
        }
        for row in rows
    ]


def get_feed(user_id: int) -> list[dict]:
    """Return self + followees' posts, newest first, with interaction data.

    Each row is a dict with keys ``post_id``, ``author_id``, ``username``,
    ``content``, ``created_at``, ``like_count``, ``liked_by_me`` and
    ``comments`` (a list of comment dicts in ascending order, see
    :func:`_comments`). Posts are ordered ``created_at DESC, id DESC``. Returns
    ``[]`` when the user follows no one and has no posts.
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
            "comments": _comments(row["id"], user_id, row["author_id"]),
        }
        for row in rows
    ]
