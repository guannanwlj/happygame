"""Follow business rules (FP-011).

Validates a follow request (logged in, target exists, not self) and delegates
the idempotent write to :func:`social_app.follows.add_follow`. This module owns
the rules only; page rendering lives in FP-010, login state in FP-003 and the
``follows`` storage in FP-004.
"""

from social_app import db
from social_app.follows import add_follow


class FollowError(Exception):
    """关注失败，message 为面向用户的可读中文原因。"""


def follow(actor_id: int | None, target_username: str) -> None:
    """Make ``actor_id`` follow the user named ``target_username``.

    Raises :class:`FollowError` when the actor is anonymous, the target does
    not exist, or the target is the actor. Duplicate follows are idempotent.
    """
    if actor_id is None:
        raise FollowError("未登录")

    row = db.query_one(
        "SELECT id FROM users WHERE username = ?", (target_username,)
    )
    if row is None:
        raise FollowError("用户不存在")

    target_id = row["id"]
    if target_id == actor_id:
        raise FollowError("不能关注自己")

    add_follow(actor_id, target_id)
