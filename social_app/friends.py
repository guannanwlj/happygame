"""我的好友列表 (my friend list) — FP-009.

Blueprint owning ``GET /friends`` (FP-002 route table fixed nav path,
label 好友列表, "查看我的好友"). The page lists the logged-in user's
friends from the symmetric ``friendships`` storage (FP-001 D-002; the rows
are written by FP-008's accept) — friend username + became-friends time
per row, newest first. Querying only the viewer's own direction renders
each friend exactly once while both sides of every pair stay visible to
their owners. Read-only: sending requests is FP-006, acting on them is
FP-008.
"""

from flask import Blueprint, render_template

from social_app import db
from social_app.auth import current_user_id, login_required

bp = Blueprint("friends", __name__)


@bp.route("/friends", methods=["GET"])
@login_required
def list_friends():
    """Render the viewer's friends, newest friendship first."""
    rows = db.query_all(
        "SELECT f.friend_id, u.username AS friend_username, f.created_at"
        " FROM friendships f JOIN users u ON u.id = f.friend_id"
        " WHERE f.user_id = ?"
        " ORDER BY f.created_at DESC, f.id DESC",
        (current_user_id(),),
    )
    return render_template("friends.html", friends=rows)
