"""Friend-post comment visibility filter (FP-003).

Pure per-post dispatch applied at the feed's comment-read convergence point
(:func:`social_app.feed._comments`): the reader's own posts and posts by
non-mutual-follow authors keep showing every comment (status quo), while
mutual-friend posts only show comments/replies whose author is inside the
visible set — the mutual friends of reader and author, plus the post author
and the reader. Top-level comments and replies are judged row by row, so a
hidden parent leaves its visible replies behind; the renderer's existing
parent-missing promotion then lifts them to top level. Any failure while
deciding returns an empty list (fail-closed — prefer showing less).

Both decision primitives are FP-001/FP-002 deliverables and derive their
answer from the live ``follows`` data, so an unfollow takes effect on the
next call (real-time fallback to the unfiltered status quo).
"""

from social_app.mutual_follows import is_mutual_follow
from social_app.mutual_friends import mutual_friend_ids


def visible_comments(post_author_id: int, viewer_id: int, comments: list) -> list:
    """Filter one post's comment rows by visibility, keeping their order.

    ``comments`` rows carry an ``author_id`` key (``sqlite3.Row`` or ``dict``).
    Dispatch: ``viewer == post_author`` or ``not is_mutual_follow(post_author,
    viewer)`` returns ``comments`` unchanged (own / non-mutual post, status
    quo); otherwise only rows whose ``author_id`` is in
    ``mutual_friend_ids(viewer, post_author) ∪ {post_author_id, viewer_id}``
    survive — each row (top-level or reply) judged independently. Any
    exception raised while deciding returns ``[]`` (fail-closed).
    """
    try:
        if viewer_id == post_author_id or not is_mutual_follow(
            post_author_id, viewer_id
        ):
            return comments
        allowed = mutual_friend_ids(viewer_id, post_author_id)
        allowed.update((post_author_id, viewer_id))
        return [row for row in comments if row["author_id"] in allowed]
    except Exception:
        return []
