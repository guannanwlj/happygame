"""Friends-feed timeline (FP-011).

``GET /feed`` aggregates all posts authored by the current user's friends,
newest first, each entry carrying author username and publish time. Only
friends' posts are visible (own and non-friend posts are excluded by the
query itself); no pagination in this version (D-decision: out of scope).
"""

from flask import Blueprint, render_template

from social_app import db
from social_app.auth import current_user_id, login_required

bp = Blueprint("feed", __name__)

# Card §3.1 core query contract, kept verbatim: the friend_id subquery is
# the visibility boundary, ORDER BY publish time DESC.
FEED_SQL = """
SELECT p.content, p.created_at, u.username
FROM posts p JOIN users u ON u.id = p.author_id
WHERE p.author_id IN (SELECT friend_id FROM friendships WHERE user_id = :current_user_id)
ORDER BY p.created_at DESC;
"""


@bp.route("/feed")
@login_required
def feed():
    """Render the friends-feed timeline for the logged-in user."""
    posts = db.query_all(FEED_SQL, {"current_user_id": current_user_id()})
    return render_template("feed.html", posts=posts)
