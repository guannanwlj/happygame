"""Posting UI for the social platform (FP-012).

Renders the post form and orchestrates submission: the login guard is
delegated to FP-003, form decoding to the FP-001 web layer, and validation /
persistence to FP-013's ``social_app.posts`` (resolved lazily so this module
imports even while that task is not mounted). A successful POST redirects to
the feed; a rejected one re-renders the form with the reason and the escaped
text preserved.
"""

import html

from social_app.app import (
    Request,
    Response,
    SocialApp,
    html_response,
    parse_form,
    redirect,
)
from social_app.session import current_user_id, require_login

POST_FORM_PATH = "/posts/new"
POST_CREATE_PATH = "/posts"
POST_SUCCESS_LOCATION = "/"
FORM_TITLE = "发布帖子"

_FORM_TEMPLATE = (
    '<form method="post" action="{action}">\n'
    '  <label for="content">内容</label>\n'
    '  <textarea id="content" name="content" rows="4" cols="60">'
    "{content}</textarea>\n"
    '  <button type="submit">发布</button>\n'
    "</form>"
)


def _load_posts():
    """Resolve the FP-013 module at call time (card §6 mock strategy)."""
    from social_app import posts

    return posts


def _form_html(content: str = "", error: str | None = None) -> str:
    """Render the post form, optionally with an escaped error banner."""
    parts: list[str] = []
    if error:
        parts.append(f'<p class="error">{html.escape(error)}</p>')
    parts.append(
        _FORM_TEMPLATE.format(
            action=POST_CREATE_PATH, content=html.escape(content)
        )
    )
    return "\n".join(parts)


def post_form(request: Request) -> Response:
    """GET /posts/new — form page, or the login redirect when anonymous."""
    guard = require_login(request)
    if guard is not None:
        return guard
    return html_response(FORM_TITLE, _form_html())


def post_submit(request: Request) -> Response:
    """POST /posts — validate through FP-013 and report the outcome."""
    guard = require_login(request)
    if guard is not None:
        return guard

    content = parse_form(request.body).get("content", "")
    posts = _load_posts()
    try:
        posts.create_post(current_user_id(request), content)
    except posts.PostError as exc:
        return html_response(FORM_TITLE, _form_html(content, str(exc)))
    return redirect(POST_SUCCESS_LOCATION)


def register(app: SocialApp) -> None:
    """Mount the post-form and submit handlers on ``app``."""
    app.route("GET", POST_FORM_PATH, post_form)
    app.route("POST", POST_CREATE_PATH, post_submit)
