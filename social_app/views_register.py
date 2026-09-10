"""Registration page for the social platform (FP-006).

Renders the username/password form at ``GET /register`` and orchestrates
``POST /register``: the submitted fields are handed to the FP-007 registration
core (``social_app.accounts.register``), which validates the account and
establishes a session. On success the visitor is redirected home with the FP-003
``session`` cookie set; on :class:`RegisterError` the form is re-rendered with
the readable reason. No validation or storage lives here.

The ``accounts`` dependency is imported lazily at the single call site so this
module imports (and is testable) before FP-007 is mounted, per task card §6.
"""

import html

from social_app.app import (
    Request,
    Response,
    html_response,
    parse_form,
    redirect,
)
from social_app.session import cookie_header

TITLE = "注册"
REGISTER_PATH = "/register"
REDIRECT_TARGET = "/"

_FORM = """<form id="register-form" method="post" action="{action}">
  <p><label>用户名 <input type="text" name="username" value="{username}"></label></p>
  <p><label>密码 <input type="password" name="password"></label></p>
  <p><button type="submit">注册</button></p>
</form>"""


def _accounts():
    """Resolve the FP-007 module at call time (card §6 substitutable)."""
    from social_app import accounts

    return accounts


def _render_form(
    username: str = "", error: str | None = None, status: int = 200
) -> Response:
    """Render the register form, optionally echoing an escaped reason."""
    blocks = []
    if error:
        blocks.append(
            f'<p class="error" role="alert">{html.escape(error, quote=True)}</p>'
        )
    blocks.append(
        _FORM.format(
            action=REGISTER_PATH, username=html.escape(username, quote=True)
        )
    )
    return html_response(TITLE, "\n".join(blocks), status=status)


def register_page(request: Request) -> Response:
    """GET /register — render an empty registration form."""
    return _render_form()


def register_submit(request: Request) -> Response:
    """POST /register — create the account and log the visitor in.

    On success return a 303 redirect to the home page carrying the session
    cookie; on a validation failure re-render the form at 200 with the reason.
    """
    fields = parse_form(request.body)
    username = fields.get("username", "")
    password = fields.get("password", "")
    accounts = _accounts()
    try:
        _user_id, token = accounts.register(username, password)
    except accounts.RegisterError as exc:
        return _render_form(username=username, error=str(exc))
    response = redirect(REDIRECT_TARGET)
    response.headers["Set-Cookie"] = cookie_header(token)
    return response


def register(app) -> None:
    """Mount the register page and submit handlers onto ``app``."""
    app.route("GET", REGISTER_PATH, register_page)
    app.route("POST", REGISTER_PATH, register_submit)
