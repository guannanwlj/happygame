"""FP-006: send a friend request (POST /friends/requests).

A logged-in user targets another user by username; after validation
(target exists -> not self -> pair not friends -> no pending request in
either direction) one ``pending`` friend_requests row is stored. ``rejected``
history never blocks a fresh send (state machine, task card §3.1).

Mounted per task card §3.2: ``bp = Blueprint("friend_request", __name__)``;
the FP-002 skeleton's ``register_blueprints`` appends the registration line
when it merges (integration point I-10). Responses are plain-text messages
(200 success / 400 validation failure) until the page skeleton and the
pending list (FP-007) exist to flash and redirect to.
"""

import sqlite3

from flask import Blueprint, request

from social_app import db
from social_app.auth import current_user_id, login_required

bp = Blueprint("friend_request", __name__)

MSG_SENT = "好友请求已发送"
MSG_USER_NOT_FOUND = "用户不存在"
MSG_SELF = "不能加自己"
MSG_ALREADY_FRIENDS = "已是好友"
MSG_PENDING_EXISTS = "已有待处理请求"


@bp.route("/friends/requests", methods=["POST"])
@login_required
def send_friend_request():
    username = (request.form.get("username") or "").strip()
    target = db.query_one("SELECT id FROM users WHERE username = ?", (username,))
    if target is None:
        return MSG_USER_NOT_FOUND, 400

    requester_id = current_user_id()
    addressee_id = target["id"]

    if addressee_id == requester_id:
        return MSG_SELF, 400

    if db.query_one(
        "SELECT 1 FROM friendships"
        " WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
        (requester_id, addressee_id, addressee_id, requester_id),
    ):
        return MSG_ALREADY_FRIENDS, 400

    if db.query_one(
        "SELECT 1 FROM friend_requests"
        " WHERE status = 'pending'"
        "   AND ((requester_id = ? AND addressee_id = ?)"
        "     OR (requester_id = ? AND addressee_id = ?))",
        (requester_id, addressee_id, addressee_id, requester_id),
    ):
        return MSG_PENDING_EXISTS, 400

    try:
        db.execute(
            "INSERT INTO friend_requests (requester_id, addressee_id)"
            " VALUES (?, ?)",
            (requester_id, addressee_id),
        )
    except sqlite3.IntegrityError:
        return MSG_PENDING_EXISTS, 400
    return MSG_SENT, 200
