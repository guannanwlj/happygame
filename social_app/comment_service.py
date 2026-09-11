"""Comment business rules (FP-018).

Validates a comment's content and delegates the write/read to the FP-016
storage layer in :mod:`social_app.comments`. This module owns the rules only:
ownership/permission checks are FP-019, HTTP handling is FP-021 and feed
rendering is FP-022.

The storage module is referenced through the module-level name ``comments`` so
tests can monkeypatch it, mirroring the dependency treatment in
:mod:`social_app.views_feed`. A module import (rather than importing the
functions by name) also avoids the collision with this module's own public
``add_comment``/``list_comments``.
"""

from social_app import comments

BLANK_CONTENT_MESSAGE = "评论内容不能为空"


class CommentError(Exception):
    """评论失败，message 为面向用户的可读中文原因。"""


def add_comment(post_id: int, author_id: int, content: str) -> int:
    """内容 strip() 后非空则保存并返回评论 id；空白抛 CommentError 且不写入。"""
    if content.strip() == "":
        raise CommentError(BLANK_CONTENT_MESSAGE)
    return comments.add_comment(post_id, author_id, content)


def list_comments(post_id: int) -> list:
    """透传存储层，按发表时间升序返回该帖评论。"""
    return comments.list_comments(post_id)
