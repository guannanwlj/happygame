"""Image serving for the social platform (FP-007, image-upload epic).

``GET /images/<storage_name>`` streams the bytes of a stored image to a
logged-in viewer (decision D-6: image URLs sit behind the FP-003 login
guard). The storage name is validated against the FP-003 directory/naming
convention (``<token>.<jpg|jpeg|png|webp>`` under ``$SOCIAL_IMAGE_DIR``) and
the file is read straight from that directory — no database is consulted
(card §3.1, URL-direct-read ruling). Illegal names and missing files answer
the same plain 404 so nothing about the disk layout leaks.
"""

import os
import re

from social_app.app import (
    Request,
    Response,
    SocialApp,
    text_response,
)
from social_app.session import require_login

IMAGE_DIR_ENV = "SOCIAL_IMAGE_DIR"
DEFAULT_IMAGE_DIR = "uploads"

IMAGE_PATH = "/images/<name>"

# Whole-string whitelist: <token>.<ext> only. Everything else — traversal
# fragments, %-encoded names, unknown or uppercase extensions — fails before
# any filesystem access.
IMAGE_NAME_RE = re.compile(r"[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)")

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def image_dir() -> str:
    """Directory holding stored images ($SOCIAL_IMAGE_DIR, or uploads/)."""
    return os.environ.get(IMAGE_DIR_ENV, DEFAULT_IMAGE_DIR)


def _not_found() -> Response:
    """Uniform 404 that never names the storage directory or the path."""
    return text_response("404 Not Found", status=404)


def serve_image(request: Request) -> Response:
    """GET /images/<name> — guard, validate the name, stream the bytes."""
    guard = require_login(request)
    if guard is not None:
        return guard

    name = request.params.get("name", "")
    if IMAGE_NAME_RE.fullmatch(name) is None:
        return _not_found()

    try:
        with open(os.path.join(image_dir(), name), "rb") as stored:
            payload = stored.read()
    except OSError:
        return _not_found()

    return Response(
        status=200,
        body=payload,
        content_type=CONTENT_TYPES[os.path.splitext(name)[1]],
    )


def register(app: SocialApp) -> None:
    """Mount the image-serving handler on ``app``."""
    app.route("GET", IMAGE_PATH, serve_image)
