"""Login & logout routes (FP-005): ``GET/POST /login`` and ``POST /logout``.

Mounted by the app factory (FP-002 shell for now) as blueprint ``login``.
Correct credentials establish the session via the FP-003 auth contract; any
credential failure renders the same unified error without a session.
"""

from flask import Blueprint, redirect, render_template, request, url_for

from social_app import auth, db

bp = Blueprint("login", __name__)

INVALID_CREDENTIALS = "用户名或密码错误"


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = db.query_one(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        )
        if user is not None and auth.verify_password(password, user["password_hash"]):
            auth.login_user(user["id"])
            return redirect(_safe_next_target(request.form.get("next", "")))
        error = INVALID_CREDENTIALS
    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    auth.logout_user()
    return redirect(url_for("login.login"))


def _safe_next_target(next_url: str) -> str:
    """Allow only same-site relative redirect targets (block open redirect).

    Accepts ``/...`` paths that are neither protocol-relative (``//host``)
    nor backslash tricks; everything else falls back to the index page.
    """
    if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
        return next_url
    return "/"
