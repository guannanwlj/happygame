"""Interaction authorization guard (FP-019).

Shared safety rule for the like and comment entry points (FP-020 / FP-021):
decide whether the current user may interact with a post. Authorized means the
post exists and the actor is its author or already follows the author. The
check is read-only — it never writes — and raises a user-facing
:class:`InteractionError` on denial so the caller can render an error page.
"""

from social_app import db
from social_app.follows import is_following

POST_NOT_FOUND_MESSAGE = "帖子不存在"
ANONYMOUS_MESSAGE = "未登录"
FORBIDDEN_MESSAGE = "无权互动该帖子"


class InteractionError(Exception):
    """互动被拒，message 为面向用户的可读中文原因。"""


def authorize_interaction(actor_id: int | None, post_id: int) -> None:
    """通过则返回 None；否则抛 InteractionError，且不产生任何写入。"""
    row = db.query_one("SELECT author_id FROM posts WHERE id = ?", (post_id,))
    if row is None:
        raise InteractionError(POST_NOT_FOUND_MESSAGE)
    if actor_id is None:
        raise InteractionError(ANONYMOUS_MESSAGE)

    author_id = row["author_id"]
    if author_id == actor_id or is_following(actor_id, author_id):
        return
    raise InteractionError(FORBIDDEN_MESSAGE)
