"""Post persistence and submission validation (FP-024, FP-002).

Thin wrapper over the generic storage API in :mod:`social_app.db`. A post is a
single ``(author_id, content)`` row in the existing ``posts`` table. On top of
the original blank-content guard, this module owns the image-era submission
rules (task card FP-002 §3.2): image count ≤ 9, extension whitelist
JPEG/PNG/WebP, per-image ≤ 5MB, and "text or at least one image". Validation
is a pure function over :class:`UploadedImage` values — parsing the multipart
body (FP-001), storing files (FP-003), and metadata rows (FP-004) live
elsewhere; the posting UI and its login guard live in FP-012
(``social_app.views_post``).
"""

import os
from dataclasses import dataclass

from social_app import db

MAX_IMAGE_COUNT = 9
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}  # 按扩展名（小写归一）判定
MAX_IMAGE_BYTES = 5 * 1024 * 1024

TOO_MANY_IMAGES_MESSAGE = "图片数量不能超过 9 张"
BAD_IMAGE_FORMAT_MESSAGE = "图片格式仅支持 JPEG/PNG/WebP"
IMAGE_TOO_LARGE_MESSAGE = "单张图片不能超过 5MB"
BLANK_CONTENT_MESSAGE = "帖子内容不能为空"


class PostError(Exception):
    """发帖失败，message 为面向用户的可读中文原因。"""


@dataclass
class UploadedImage:
    """一张待上传图片：文件名＋原始字节（size = len(data)）。"""

    filename: str
    data: bytes


def validate_post_submission(content: str, images: list[UploadedImage]) -> None:
    """按固定顺序 ①→④ 校验发帖提交，全部通过返回 None，先命中先报。

    ① 图片数量超上限；② 任一扩展名不在白名单（整列表先于大小判定）；
    ③ 任一字节数超上限；④ 文本空白且无图片。
    """
    if len(images) > MAX_IMAGE_COUNT:
        raise PostError(TOO_MANY_IMAGES_MESSAGE)
    if any(
        os.path.splitext(image.filename)[1].lower() not in IMAGE_EXTENSIONS
        for image in images
    ):
        raise PostError(BAD_IMAGE_FORMAT_MESSAGE)
    if any(len(image.data) > MAX_IMAGE_BYTES for image in images):
        raise PostError(IMAGE_TOO_LARGE_MESSAGE)
    if content.strip() == "" and not images:
        raise PostError(BLANK_CONTENT_MESSAGE)


def create_post(author_id: int, content: str, image_count: int = 0) -> int:
    """写入 posts 并返回新帖子 id。

    content 空白且 image_count==0 → PostError（不写入）；content 空白且
    image_count>0 → 照常写入（D-1 纯图帖，content 原样存储）。image_count
    默认 0，既有调用方与既有测试零改动。
    """
    if content.strip() == "" and image_count == 0:
        raise PostError(BLANK_CONTENT_MESSAGE)
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (author_id, content),
    )
    return cur.lastrowid
