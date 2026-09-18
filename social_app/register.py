"""User registration (FP-004).

Registration page and form flow on blueprint ``bp`` — mounted by the FP-002
skeleton's ``register_blueprints`` registry via
``app.register_blueprint(register.bp)``. Credentials are 用户名+密码 (D-004);
only the FP-003 contract hash of the password is stored (never plaintext) in
the FP-001 ``users`` table. On success the user is handed over to ``/login``
(FP-005 owns the login flow itself — no auto-login here).
"""

import re
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request

from . import db
from .auth import hash_password

bp = Blueprint("register", __name__)

USERNAME_MIN = 3
USERNAME_MAX = 30
PASSWORD_MIN = 6
PASSWORD_MAX = 128
USERNAME_CHARS_RE = re.compile(r"^[A-Za-z0-9_]+$")

USERNAME_REQUIRED = "用户名不能为空"
USERNAME_INVALID = "用户名须为 3–30 个字符，仅限字母、数字和下划线"
USERNAME_TAKEN = "用户名已被占用"
PASSWORD_INVALID = "密码长度须为 6–128 个字符"
SUCCESS_MESSAGE = "注册成功，请登录"

LOGIN_URL = "/login"  # route owned by FP-005; 404 until it merges


def username_exists(username: str) -> bool:
    """Return True when ``username`` is already taken (friendly pre-check)."""
    row = db.query_one("SELECT 1 FROM users WHERE username = ?", (username,))
    return row is not None


def create_user(username: str, password: str) -> int:
    """Insert a new credential row; store only the hash of ``password``."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, hash_password(password)),
    )
    return cur.lastrowid


def validate_registration(username: str, password: str) -> str | None:
    """Return the first error message for the submission, or None if valid."""
    if not username:
        return USERNAME_REQUIRED
    if not (
        USERNAME_MIN <= len(username) <= USERNAME_MAX
        and USERNAME_CHARS_RE.fullmatch(username)
    ):
        return USERNAME_INVALID
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        return PASSWORD_INVALID
    if username_exists(username):
        return USERNAME_TAKEN
    return None


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Show the registration form; create the account on a valid submit."""
    if request.method == "GET":
        return render_template("register.html", error=None, username="")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    error = validate_registration(username, password)
    if error is None:
        try:
            create_user(username, password)
        except sqlite3.IntegrityError:
            error = USERNAME_TAKEN  # UNIQUE race lost despite the pre-check
        else:
            flash(SUCCESS_MESSAGE)
            return redirect(LOGIN_URL)
    return render_template("register.html", error=error, username=username)
