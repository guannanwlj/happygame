"""接受/拒绝好友请求 (accept/reject friend request) — FP-008.

Blueprint owning the two variable-path action routes
``/friends/requests/<int:req_id>/accept|reject`` (FP-002 route table;
entries addressed by request id from the FP-007 pending list page,
INTEGRATION.md I-17). Only the **addressee** of a ``pending`` request may
act: accept flips it to ``accepted`` and writes both symmetric friendship
rows in one transaction (FP-001 D-002); reject flips it to ``rejected``
without touching friendships. Every non-actionable case (unknown id, wrong
addressee, already processed) is a uniform 404 with zero state change.
After either action: flash + 303 redirect back to the pending list (PRG).
"""

from flask import Blueprint, abort, flash, redirect

from social_app import db
from social_app.auth import current_user_id, login_required

bp = Blueprint("friend_request_actions", __name__)

MSG_ACCEPTED = "好友请求已接受"
MSG_REJECTED = "好友请求已拒绝"

LIST_PATH = "/friends/requests"
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"
_GUARDED_UPDATE = (
    f"UPDATE friend_requests SET status = ?, updated_at = {_NOW}"
    " WHERE id = ? AND addressee_id = ? AND status = 'pending'"
)


def _back_to_list(message: str):
    """Flash the outcome and send the viewer back to the pending list (PRG)."""
    flash(message)
    return redirect(LIST_PATH, code=303)


@bp.route("/friends/requests/<int:req_id>/accept", methods=("GET", "POST"))
@login_required
def accept_request(req_id: int):
    """Mark the addressed pending request accepted and befriend both sides."""
    addressee_id = current_user_id()
    with db.transaction() as conn:
        cur = conn.execute(_GUARDED_UPDATE, ("accepted", req_id, addressee_id))
        if cur.rowcount != 1:
            abort(404)  # rolls the transaction back, nothing was written
        requester_id = conn.execute(
            "SELECT requester_id FROM friend_requests WHERE id = ?", (req_id,)
        ).fetchone()["requester_id"]
        for user_id, friend_id in (
            (addressee_id, requester_id),
            (requester_id, addressee_id),
        ):
            conn.execute(
                "INSERT OR IGNORE INTO friendships (user_id, friend_id)"
                " VALUES (?, ?)",
                (user_id, friend_id),
            )
    return _back_to_list(MSG_ACCEPTED)


@bp.route("/friends/requests/<int:req_id>/reject", methods=("GET", "POST"))
@login_required
def reject_request(req_id: int):
    """Mark the addressed pending request rejected; no friendship is created."""
    cur = db.execute(_GUARDED_UPDATE, ("rejected", req_id, current_user_id()))
    if cur.rowcount != 1:
        abort(404)
    return _back_to_list(MSG_REJECTED)
