"""HTTP layer for authentication & sessions (FP-003).

Thin JSON endpoints over the domain functions in social_app.auth. The domain
functions are imported into module scope so tests can monkeypatch them (mock
isolation) and exercise endpoint behavior without a database.
"""

import functools

from flask import Blueprint, jsonify, request, session

from social_app import auth
from social_app.auth import (
    ValidationError,
    authenticate,
    register_user,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

AUTHENTICATION_REQUIRED = "authentication required"


def user_payload(row) -> dict:
    """Public JSON shape of a user (never exposes password material)."""
    return {"id": row["id"], "username": row["username"]}


def fetch_credentials() -> tuple:
    """Extract (username, password) from the JSON request body.

    Raises ValidationError for a non-object body or missing fields.
    """
    body = request.get_json()
    if not isinstance(body, dict):
        raise ValidationError("request body must be a JSON object")
    missing = [field for field in ("username", "password") if field not in body]
    if missing:
        raise ValidationError(f"missing required field(s): {', '.join(missing)}")
    return body["username"], body["password"]


@auth_bp.post("/register")
def register():
    username, password = fetch_credentials()
    row = register_user(username, password)
    return jsonify(user_payload(row)), 201


@auth_bp.post("/login")
def login():
    username, password = fetch_credentials()
    row = authenticate(username, password)
    auth.login_session(session, row["id"])
    return jsonify(user_payload(row))


@auth_bp.post("/logout")
def logout():
    auth.logout_session(session)
    return jsonify({"ok": True})


@auth_bp.get("/me")
def me():
    row = auth.current_user(session)
    if row is None:
        return jsonify({"error": AUTHENTICATION_REQUIRED}), 401
    return jsonify(user_payload(row))


def login_required(view):
    """Reject anonymous requests with a 401 JSON body.

    Authenticated calls invoke the view with an extra ``user_id`` keyword.
    """

    @functools.wraps(view)
    def wrapped(**kwargs):
        user_id = auth.session_user_id(session)
        if user_id is None:
            return jsonify({"error": AUTHENTICATION_REQUIRED}), 401
        return view(user_id=user_id, **kwargs)

    return wrapped
