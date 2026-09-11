"""Post persistence (FP-024).

Thin wrapper over the generic storage API in :mod:`social_app.db`. A post is a
single ``(author_id, content)`` row in the existing ``posts`` table. This module
provides only validation (non-blank content) and the write; the posting UI and
its login guard live in FP-012 (``social_app.views_post``).
"""

from social_app import db

BLANK_CONTENT_MESSAGE = "帖子内容不能为空"


class PostError(Exception):
    """发帖失败，message 为面向用户的可读中文原因。"""


def create_post(author_id: int, content: str) -> int:
    """内容去首尾空白后非空则写入 posts，返回新帖子 id；空白抛 PostError 且不写入。"""
    if content.strip() == "":
        raise PostError(BLANK_CONTENT_MESSAGE)
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (author_id, content),
    )
    return cur.lastrowid
