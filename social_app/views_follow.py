"""Follow operation UI (FP-010).

Serves the follow entry point as ``POST /follow``: a logged-in user submits a
target username and the page reports the outcome. Validation and the write
live in FP-011 (:mod:`social_app.follow_service`); this module only guards the
route (FP-003), parses the form (FP-001) and renders the feedback, escaping
every echoed value.
"""

import html

from social_app import follow_service
from social_app.app import Response, html_response, parse_form
from social_app.session import current_user_id, require_login

FOLLOW_PATH = "/follow"
HOME_PATH = "/"
TARGET_FIELD = "target_username"

SUCCESS_MESSAGE = "关注成功"
FAILURE_MESSAGE = "关注失败"


def _feedback_page(
    title: str, message: str, target_username: str, variant: str
) -> Response:
    """Render the shared result page (title escaped by ``html_response``)."""
    body = (
        f'<section id="follow-result" class="{variant}">\n'
        f"  <p>{html.escape(message)}</p>\n"
        f"  <p>目标用户：{html.escape(target_username)}</p>\n"
        f'  <p><a href="{HOME_PATH}">返回首页</a></p>\n'
        "</section>"
    )
    return html_response(title, body)


def follow_submit(request) -> Response:
    """Handle ``POST /follow``: guard, validate via FP-011, render result."""
    denied = require_login(request)
    if denied is not None:
        return denied

    fields = parse_form(request.body)
    target_username = fields.get(TARGET_FIELD, "")
    actor_id = current_user_id(request)

    try:
        follow_service.follow(actor_id, target_username)
    except follow_service.FollowError as exc:
        message = f"{FAILURE_MESSAGE}：{exc}"
        return _feedback_page(FAILURE_MESSAGE, message, target_username, "error")

    message = f"{SUCCESS_MESSAGE}：你已关注该用户。"
    return _feedback_page(SUCCESS_MESSAGE, message, target_username, "success")


def register(app) -> None:
    """Mount the follow handler on ``app`` (``POST /follow``)."""
    app.route("POST", FOLLOW_PATH, follow_submit)
