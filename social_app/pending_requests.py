"""好友请求待处理列表 (pending friend request list) — FP-007.

Blueprint owning ``GET /friends/requests`` (FP-006 owns the POST on the
same path; disjoint methods coexist in the URL map). The page lists the
``pending`` friend requests **addressed to** the logged-in user — requester
username + request time per row, plus accept/reject entry links addressed
by request id (FP-008's targets, INTEGRATION.md I-17: the variable paths
are reachable only from this list page). Read-only: acting on a request is
FP-008, sending one is FP-006.
"""

from flask import Blueprint, render_template

from social_app import db
from social_app.auth import current_user_id, login_required

bp = Blueprint("pending_requests", __name__)


@bp.route("/friends/requests", methods=["GET"])
@login_required
def list_pending_requests():
    """Render the viewer's pending incoming friend requests, newest first."""
    rows = db.query_all(
        "SELECT fr.id, fr.created_at, u.username AS requester_username"
        " FROM friend_requests fr JOIN users u ON u.id = fr.requester_id"
        " WHERE fr.addressee_id = ? AND fr.status = 'pending'"
        " ORDER BY fr.created_at DESC, fr.id DESC",
        (current_user_id(),),
    )
    return render_template("pending_requests.html", requests=rows)
