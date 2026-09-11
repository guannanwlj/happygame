"""Comment-dimension interaction submit routes (FP-004).

Mounts three POST routes under a comment:

* ``POST /comments/<id>/like``
* ``POST /comments/<id>/unlike``
* ``POST /comments/<id>/replies``

Each runs the same orchestration as the post routes in
:mod:`social_app.views_like` / :mod:`social_app.views_comment`: login guard
(FP-003), comment interaction authorization (FP-003) and the relevant service
(FP-006 comment likes / FP-008 replies), then redirects to the feed. This module
owns HTTP orchestration and rendering only — it never touches the database.
"""

import html

from social_app.app import Response, html_response, parse_form, redirect
from social_app.interaction_service import (
    InteractionError,
    authorize_comment_interaction,
)
from social_app.session import current_user_id, require_login

COMMENT_LIKE_PATH = "/comments/<id>/like"
COMMENT_UNLIKE_PATH = "/comments/<id>/unlike"
COMMENT_REPLY_PATH = "/comments/<id>/replies"
HOME_PATH = "/"
CONTENT_FIELD = "content"
ERROR_TITLE = "操作失败"

# FP-006 provides the like service; until it lands, fall back to FP-001's
# storage primitives (card §6). The signatures match the real contract.
try:
    from social_app.comment_like_service import like_comment, unlike_comment
except ImportError:  # pragma: no cover - exercised only before FP-006 lands
    from social_app.comment_likes import (
        add_comment_like,
        count_comment_likes,
        remove_comment_like,
    )

    def like_comment(actor_id: int, comment_id: int) -> int:
        """Idempotently like ``comment_id``; return the new total."""
        add_comment_like(actor_id, comment_id)
        return count_comment_likes(comment_id)

    def unlike_comment(actor_id: int, comment_id: int) -> int:
        """Idempotently unlike ``comment_id``; return the new total."""
        remove_comment_like(actor_id, comment_id)
        return count_comment_likes(comment_id)


# FP-008 provides the reply service; until it lands, fall back to FP-016
# storage with the minimum validation rules (card §6).
try:
    from social_app.reply_service import ReplyError, add_reply
except ImportError:  # pragma: no cover - exercised only before FP-008 lands
    from social_app import comments as _comments

    PARENT_NOT_FOUND_MESSAGE = "父评论不存在"
    PARENT_NOT_TOP_LEVEL_MESSAGE = "只能回复顶层评论"
    BLANK_REPLY_MESSAGE = "回复内容不能为空"

    class ReplyError(Exception):
        """回复失败，message 为面向用户的可读中文原因。"""

    def add_reply(parent_id: int, author_id: int, content: str) -> int:
        """Reply to a top-level comment and return the new reply id."""
        if content.strip() == "":
            raise ReplyError(BLANK_REPLY_MESSAGE)
        parent = _comments.get_comment(parent_id)
        if parent is None:
            raise ReplyError(PARENT_NOT_FOUND_MESSAGE)
        if parent["parent_id"] is not None:
            raise ReplyError(PARENT_NOT_TOP_LEVEL_MESSAGE)
        return _comments.add_comment(
            parent["post_id"], author_id, content, parent_id=parent_id
        )


def _error_page(exc: Exception) -> Response:
    """Render a readable failure page with an escaped reason and a home link."""
    body = (
        '<section id="comment-interaction-error" class="error">\n'
        f"  <p>{html.escape(str(exc))}</p>\n"
        f'  <p><a href="{HOME_PATH}">返回首页</a></p>\n'
        "</section>"
    )
    return html_response(ERROR_TITLE, body)


def _submit_like(request, operation) -> Response:
    """Shared like/unlike flow: login guard → authorize → service → 303 home."""
    denied = require_login(request)
    if denied is not None:
        return denied

    comment_id = int(request.params["id"])
    actor_id = current_user_id(request)
    try:
        authorize_comment_interaction(actor_id, comment_id)
        operation(actor_id, comment_id)
    except InteractionError as exc:
        return _error_page(exc)
    return redirect(HOME_PATH)


def comment_like_submit(request) -> Response:
    """Handle ``POST /comments/<id>/like``."""
    return _submit_like(request, like_comment)


def comment_unlike_submit(request) -> Response:
    """Handle ``POST /comments/<id>/unlike``."""
    return _submit_like(request, unlike_comment)


def comment_reply_submit(request) -> Response:
    """Handle ``POST /comments/<id>/replies``: guard, authorize, write, redirect."""
    denied = require_login(request)
    if denied is not None:
        return denied

    parent_id = int(request.params["id"])
    content = parse_form(request.body).get(CONTENT_FIELD, "")
    actor_id = current_user_id(request)
    try:
        authorize_comment_interaction(actor_id, parent_id)
        add_reply(parent_id, actor_id, content)
    except (InteractionError, ReplyError) as exc:
        return _error_page(exc)
    return redirect(HOME_PATH)


def register(app) -> None:
    """Mount all three comment interaction routes on ``app``."""
    app.route("POST", COMMENT_LIKE_PATH, comment_like_submit)
    app.route("POST", COMMENT_UNLIKE_PATH, comment_unlike_submit)
    app.route("POST", COMMENT_REPLY_PATH, comment_reply_submit)
