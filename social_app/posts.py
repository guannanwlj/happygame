"""发布帖子 (create post) — FP-010.

Blueprint mounted at ``/posts/new`` (FP-002 mounting contract). Logged-in
users submit plain text (D-003); content is trimmed, must be non-empty and
at most ``CONTENT_MAX_LEN`` characters. Valid posts are stored via FP-001
with the DB default ``created_at``. No edit or delete is offered (D-006).
"""

from flask import Blueprint, flash, redirect, render_template, request

from social_app.auth import current_user_id, login_required
from social_app import db

bp = Blueprint("posts", __name__)

CONTENT_MAX_LEN = 1000
EMPTY_REASON = "帖子内容不能为空"
TOO_LONG_REASON = f"帖子内容不能超过 {CONTENT_MAX_LEN} 字符"


@bp.route("/posts/new", methods=["GET", "POST"])
@login_required
def new_post():
    """Compose (GET) and publish (POST) a plain-text post."""
    if request.method == "GET":
        return render_template("posts/new.html")

    content = request.form.get("content", "").strip()
    error = None
    if not content:
        error = EMPTY_REASON
    elif len(content) > CONTENT_MAX_LEN:
        error = TOO_LONG_REASON
    if error:
        return render_template("posts/new.html", error=error, content=content), 422

    db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (current_user_id(), content),
    )
    flash("帖子已发布")
    return redirect("/posts/new", code=303)
