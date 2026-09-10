"""Login page and logout views (FP-008).

Server-rendered login form plus the logout entry for the social platform.
This module owns the HTTP surface only: it parses the submitted form,
delegates credential checking to FP-009 (``social_app.auth.login``), and on
success attaches the FP-003 session cookie; logout invalidates the session
token through FP-003 and clears the cookie. No database access and no
password logic live here.

Both authentication failures (unknown username and wrong password) surface
as the same ``认证失败`` message so the page cannot be used to enumerate
accounts. The three routes are mounted over the FP-001 skeleton 501
placeholders by ``register(app)`` from ``create_app()``.
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
from social_app.session import (
    SESSION_COOKIE,
    clear_cookie_header,
    cookie_header,
    destroy_session,
)

LOGIN_PATH = "/login"
LOGOUT_PATH = "/logout"
HOME_PATH = "/"
LOGIN_TITLE = "登录"
FAILURE_MESSAGE = "认证失败"


def login(username: str, password: str) -> str | None:
    """Authenticate through FP-009, returning a session token or ``None``.

    The FP-009 module is resolved at call time (card §6) so tests can
    monkeypatch ``social_app.views_login.login`` and so this page keeps
    working unchanged once ``social_app.auth`` lands. A missing
    implementation fails closed with ``None``.
    """
    try:
        from social_app import auth
    except ImportError:
        return None
    return auth.login(username, password)


def _login_body(username: str = "", error: str | None = None) -> str:
    """Render the login form fragment (plus the logout entry)."""
    rows = ['<section id="login">']
    if error:
        rows.append(f'<p class="error" role="alert">{html.escape(error)}</p>')
    rows.append(
        f'<form method="post" action="{LOGIN_PATH}">'
        '<label for="username">用户名</label>'
        f'<input id="username" name="username" '
        f'value="{html.escape(username)}" required>'
        '<label for="password">密码</label>'
        '<input id="password" type="password" name="password" required>'
        '<button type="submit">登录</button>'
        "</form>"
    )
    rows.append(
        f'<form method="post" action="{LOGOUT_PATH}">'
        '<button type="submit">退出登录</button>'
        "</form>"
    )
    rows.append("</section>")
    return "\n".join(rows)


def _render_login(username: str = "", error: str | None = None) -> Response:
    return html_response(LOGIN_TITLE, _login_body(username, error))


def login_page(_request: Request) -> Response:
    """GET /login — render the empty login form."""
    return _render_login()


def login_submit(request: Request) -> Response:
    """POST /login — authenticate and redirect, or re-render on failure."""
    fields = parse_form(request.body)
    username = fields.get("username", "")
    password = fields.get("password", "")
    token = login(username, password)
    if token is None:
        return _render_login(username, FAILURE_MESSAGE)
    response = redirect(HOME_PATH)
    response.headers["Set-Cookie"] = cookie_header(token)
    return response


def logout(request: Request) -> Response:
    """POST /logout — invalidate the session and clear the cookie."""
    destroy_session(request.cookies.get(SESSION_COOKIE))
    response = redirect(LOGIN_PATH)
    response.headers["Set-Cookie"] = clear_cookie_header()
    return response


def register(app: SocialApp) -> None:
    """Mount GET /login, POST /login and POST /logout on ``app``."""
    app.route("GET", LOGIN_PATH, login_page)
    app.route("POST", LOGIN_PATH, login_submit)
    app.route("POST", LOGOUT_PATH, logout)
