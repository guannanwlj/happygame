"""Local-disk image file storage (FP-003).

Validated image bytes are persisted under the directory named by the
``SOCIAL_IMAGE_DIR`` environment variable (read at call time, mirroring the
``SOCIAL_DB`` pattern in :mod:`social_app.db`), defaulting to ``uploads``
relative to the current working directory. Each file is named
``<random token>.<ext>`` where the extension is the lower-cased suffix of
the original upload filename; a name collision regenerates the token, so a
repeated upload never overwrites an existing file.

The ``storage_name`` returned by :func:`save_image` is the shared contract
across the upload chain: FP-004 stores it in the ``post_images`` metadata
table and FP-007 serves the file as ``/images/<storage_name>``. Any failure
raises :class:`ImageStorageError` after deleting this call's partial temp
file, leaving no residue in the target directory so the caller can roll
back the whole post (FP-006).
"""

import os
import secrets

IMAGE_DIR_ENV = "SOCIAL_IMAGE_DIR"
DEFAULT_IMAGE_DIR = "uploads"


class ImageStorageError(Exception):
    """图片存储失败，message 为可读中文原因（如目录不可写、写入失败）。"""


def image_dir() -> str:
    """Return $SOCIAL_IMAGE_DIR or the default directory (call-time read)."""
    return os.environ.get(IMAGE_DIR_ENV, DEFAULT_IMAGE_DIR)


def _discard(path: str) -> None:
    """Best-effort unlink so a failed save leaves no partial file behind."""
    try:
        os.unlink(path)
    except OSError:
        pass


def save_image(data: bytes, original_filename: str) -> str:
    """Write ``data`` into a new file under ``image_dir()``.

    Returns the ``storage_name`` (file name only, no directory part). The
    target directory is created when missing; a colliding name is regenerated.
    Raises :class:`ImageStorageError` — after deleting this call's partial
    temp file — when the directory is unusable or the write fails.
    """
    directory = image_dir()
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise ImageStorageError(f"图片存储目录不可用：{directory}（{exc}）") from exc

    ext = os.path.splitext(original_filename)[1].lower()
    while True:
        storage_name = f"{secrets.token_urlsafe(16)}{ext}"
        target = os.path.join(directory, storage_name)
        temp_path = os.path.join(directory, f".{storage_name}.part")
        try:
            if os.path.exists(target):
                continue
            fd = os.open(
                temp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
            )
        except FileExistsError:
            continue
        except OSError as exc:
            raise ImageStorageError(f"图片写入失败：{exc}") from exc
        try:
            try:
                remaining = memoryview(data)
                while remaining:
                    remaining = remaining[os.write(fd, remaining) :]
                os.replace(temp_path, target)
            finally:
                os.close(fd)
        except OSError as exc:
            _discard(temp_path)
            raise ImageStorageError(f"图片写入失败：{exc}") from exc
        return storage_name
