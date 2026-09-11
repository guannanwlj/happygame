"""Comment submit route (FP-021).

Mounts ``POST /posts/<id>/comments``: guard the request through FP-003
(:mod:`social_app.session`), authorize the interaction through FP-019, hand the
content to the FP-018 comment service and redirect home (303). A denied guard or
authorization, or a rejected comment, renders a readable error page. This module
owns orchestration and rendering only — it never touches the database, and the
feed's comment list is rendered by FP-022.
"""

import html

from social_app.app import Response, html_response, parse_form, redirect
from social_app.comment_service import CommentError, add_comment
from social_app.interaction_service import InteractionError, authorize_interaction
from social_app.session import current_user_id, require_login

COMMENTS_PATH = "/posts/<id>/comments"
HOME_PATH = "/"
CONTENT_FIELD = "content"
ERROR_TITLE = "评论失败"


def _error_page(message: str) -> Response:
    """Render a readable error page with an escaped reason and a home link."""
    body = (
        '<section id="comment-error" class="error">\n'
        f"  <p>{html.escape(message)}</p>\n"
        f'  <p><a href="{HOME_PATH}">返回首页</a></p>\n'
        "</section>"
    )
    return html_response(ERROR_TITLE, body)


def comment_submit(request) -> Response:
    """Handle ``POST /posts/<id>/comments``: guard, authorize, write, redirect."""
    denied = require_login(request)
    if denied is not None:
        return denied

    post_id = int(request.params["id"])
    content = parse_form(request.body).get(CONTENT_FIELD, "")
    actor_id = current_user_id(request)

    try:
        authorize_interaction(actor_id, post_id)
        add_comment(post_id, actor_id, content)
    except (InteractionError, CommentError) as exc:
        return _error_page(str(exc))
    return redirect(HOME_PATH)


def register(app) -> None:
    """Mount the comment submit handler on ``app`` (``POST /posts/<id>/comments``)."""
    app.route("POST", COMMENTS_PATH, comment_submit)
