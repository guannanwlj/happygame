"""Like / unlike HTTP entry points (FP-020).

Mounts ``POST /posts/<id>/like`` and ``POST /posts/<id>/unlike``: a logged-in
user is funneled through the login guard (FP-003), the interaction
authorization guard (FP-019) and the like service (FP-017), then redirected
back to the feed. This module owns the HTTP orchestration only — it never
touches the database and never renders like counts (FP-022).
"""

import html

from social_app.app import Response, html_response, redirect
from social_app.interaction_service import InteractionError, authorize_interaction
from social_app.like_service import like, unlike
from social_app.session import current_user_id, require_login

LIKE_PATH = "/posts/<id>/like"
UNLIKE_PATH = "/posts/<id>/unlike"
HOME_PATH = "/"
ERROR_TITLE = "操作失败"


def _error_page(exc: Exception) -> Response:
    """Render a readable failure page for a denied interaction (link home)."""
    body = (
        '<section id="like-error" class="error">\n'
        f"  <p>{html.escape(str(exc))}</p>\n"
        f'  <p><a href="{HOME_PATH}">返回首页</a></p>\n'
        "</section>"
    )
    return html_response(ERROR_TITLE, body)


def _submit(request, operation) -> Response:
    """Shared flow: login guard → authorize → service → 303 home."""
    denied = require_login(request)
    if denied is not None:
        return denied

    post_id = int(request.params["id"])
    actor_id = current_user_id(request)
    try:
        authorize_interaction(actor_id, post_id)
        operation(actor_id, post_id)
    except InteractionError as exc:
        return _error_page(exc)
    return redirect(HOME_PATH)


def like_submit(request) -> Response:
    """Handle ``POST /posts/<id>/like``."""
    return _submit(request, like)


def unlike_submit(request) -> Response:
    """Handle ``POST /posts/<id>/unlike``."""
    return _submit(request, unlike)


def register(app) -> None:
    """Mount both like routes on ``app``."""
    app.route("POST", LIKE_PATH, like_submit)
    app.route("POST", UNLIKE_PATH, unlike_submit)
