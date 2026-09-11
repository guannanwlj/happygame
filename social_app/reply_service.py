"""Reply business rules (FP-008).

Validates a reply and delegates the write/read to the FP-002/FP-016 storage
layer in :mod:`social_app.comments`. The platform keeps replies one level deep:
only a top-level comment (``parent_id IS NULL``) may be replied to. Content must
be non-blank after ``strip()``. Replying to one's own comment is allowed (D6).
A failed check raises :class:`ReplyError` with a user-facing Chinese reason and
performs no write.

The storage module is referenced through the module-level name ``comments`` so
tests can monkeypatch it, mirroring :mod:`social_app.comment_service`.
"""

from social_app import comments

PARENT_NOT_FOUND_MESSAGE = "回复对象不存在"
NOT_TOP_LEVEL_MESSAGE = "只能回复顶层评论"
BLANK_CONTENT_MESSAGE = "回复内容不能为空"


class ReplyError(Exception):
    """回复失败，message 为面向用户的可读中文原因。"""


def add_reply(parent_id: int, author_id: int, content: str) -> int:
    """校验通过则写入回复并返回新 id；否则抛 ReplyError 且不写入。

    校验顺序（§4）：父评论存在 → 父评论为顶层 → 内容 strip() 后非空。
    写入时 post_id 取自父评论，parent_id 为传入的 parent_id。
    """
    parent = comments.get_comment(parent_id)
    if parent is None:
        raise ReplyError(PARENT_NOT_FOUND_MESSAGE)
    if parent["parent_id"] is not None:
        raise ReplyError(NOT_TOP_LEVEL_MESSAGE)
    if content.strip() == "":
        raise ReplyError(BLANK_CONTENT_MESSAGE)
    return comments.add_comment(
        parent["post_id"], author_id, content, parent_id=parent_id
    )
