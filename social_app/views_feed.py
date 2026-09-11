"""Feed page and empty state (FP-014).

Makes ``GET /`` the home feed: guard the request through FP-003
(:mod:`social_app.session`), fetch the followed users' posts through FP-005
(:mod:`social_app.feed`) and render them newest-first. With no posts the page
shows an empty-state guide, and anonymous visitors are sent to ``/login``.

FP-022 extends the per-post rendering with the interaction layer: the like
total, the viewer's like/unlike form (from the FP-023 row's ``like_count`` /
``liked_by_me``) and the comment form plus list (``comments``). The forms point
at the FP-020/FP-021 routes; this module only renders them.

FP-009 extends comment rendering: comments are split into top-level entries and
replies by ``parent_id``, replies are nested one level under their parent, and
each comment shows its like count and the viewer's comment-like state. FP-005
renders that comment-like control through ``_render_comment_likes`` (the
like/unlike form pointing at the FP-004 routes). FP-007's ``_render_reply_form``
/ ``_render_replies`` are consumed when they exist and replaced by small local
fallbacks otherwise (card §6), so the module stays independently renderable.

This module owns orchestration and rendering only; no database access and no
pagination (card §4/§5). The dependencies are imported as module globals so the
card §6 tests can monkeypatch them; until FP-005 lands, ``get_feed`` falls back
to an empty result so the page still renders its empty state.
"""

import html

from social_app.app import Response, html_response
from social_app.session import current_user_id, require_login

try:  # FP-005 contract (card §3.2); stub keeps this module importable until then
    from social_app.feed import get_feed
except ImportError:  # pragma: no cover - exercised only before FP-005 lands

    def get_feed(user_id: int) -> list:
        return []


FEED_TITLE = "首页 / 帖流"

EMPTY_STATE_HTML = (
    '<section id="feed-empty" class="empty-state">\n'
    "  <p>你的帖流还是空的。</p>\n"
    '  <p>去<a href="/posts/new">发帖</a>，或先关注其他用户来充实这里。</p>\n'
    "</section>"
)


def _row_value(row, key: str, default=None):
    """Read ``key`` from a ``sqlite3.Row``/``dict`` or a mock namespace.

    Missing keys return ``default`` so FP-014 rows without interaction columns
    keep rendering (card §4). The raw value is returned (not stringified) so
    ``liked_by_me`` keeps its boolean type.
    """
    try:
        value = row[key]
    except (TypeError, KeyError, IndexError):
        value = getattr(row, key, default)
    return default if value is None else value


def _escaped(row, key: str, default="") -> str:
    """Read ``key`` and HTML-escape it for a text node or attribute."""
    return html.escape(str(_row_value(row, key, default)))


def _render_likes(row) -> str:
    """Render the like total and the like/unlike form for one post."""
    post_id = _escaped(row, "post_id")
    like_count = _escaped(row, "like_count", 0)
    if _row_value(row, "liked_by_me", False):
        action, label = f"/posts/{post_id}/unlike", "取消点赞"
    else:
        action, label = f"/posts/{post_id}/like", "点赞"
    return (
        '<div class="post-likes">\n'
        f'  <span class="like-count">{like_count}</span>\n'
        f'  <form class="like-form" action="{action}" method="post">\n'
        f'    <button type="submit">{label}</button>\n'
        "  </form>\n"
        "</div>"
    )


def _render_comment_likes(entry) -> str:
    """Render a comment's like total and the viewer's like/unlike form.

    ``like_count`` / ``liked_by_me`` default to ``0`` / ``False`` so comment
    rows without the FP-009 fields still render (card §4). The form targets the
    FP-004 routes; this module only renders them (card §5).
    """
    comment_id = _escaped(entry, "comment_id")
    like_count = _escaped(entry, "like_count", 0)
    liked = bool(_row_value(entry, "liked_by_me", False))
    if liked:
        action, label = f"/comments/{comment_id}/unlike", "取消点赞"
    else:
        action, label = f"/comments/{comment_id}/like", "点赞"
    state = "已赞" if liked else "未赞"
    return (
        '<div class="comment-likes">\n'
        f'  <span class="comment-like-count">{like_count}</span>\n'
        f'  <span class="comment-liked-state">{state}</span>\n'
        f'  <form class="comment-like-form" action="{action}" method="post">\n'
        f'    <button type="submit">{label}</button>\n'
        "  </form>\n"
        "</div>"
    )


def _fallback_reply_form(entry) -> str:
    """No reply entry point until FP-007 provides one (card §6)."""
    return ""


def _fallback_replies(entry, replies) -> str:
    """Render a parent comment's replies until FP-007 provides the list."""
    items = "\n".join(_render_comment(reply, is_reply=True) for reply in replies)
    return f'<ul class="reply-list">\n{items}\n</ul>'


# FP-007 (``_render_reply_form`` / ``_render_replies``) owns the real
# implementations. Until it lands these names resolve to the local fallbacks,
# keeping the documented contract resolvable and monkeypatchable while this
# module stays independently renderable (card §6). FP-005's
# ``_render_comment_likes`` is defined above.
_render_reply_form = _fallback_reply_form
_render_replies = _fallback_replies


def _split_comments(comments) -> tuple[list, dict]:
    """Split comments into top-level entries and replies grouped by parent.

    A reply whose parent is not a known top-level comment (legacy or malformed
    data) is promoted to top-level rather than dropped. Replies are never
    nested more than one level (card §2).
    """
    top_ids = {
        _row_value(entry, "comment_id", None)
        for entry in comments
        if _row_value(entry, "parent_id", None) is None
    }
    tops: list = []
    replies_by_parent: dict = {}
    for entry in comments:
        parent_id = _row_value(entry, "parent_id", None)
        if parent_id is None or parent_id not in top_ids:
            tops.append(entry)
        else:
            replies_by_parent.setdefault(parent_id, []).append(entry)
    return tops, replies_by_parent


def _render_comment(entry, replies=(), *, is_reply=False) -> str:
    """Render one escaped ``<li>``; nest ``replies`` under a top-level entry."""
    author = _escaped(entry, "author")
    created_at = _escaped(entry, "created_at")
    content = _escaped(entry, "content")
    css_class = "comment reply" if is_reply else "comment"
    lines = [
        f'<li class="{css_class}">',
        f'  <span class="comment-author">{author}</span>',
        f'  <time class="comment-time" datetime="{created_at}">{created_at}</time>',
        f'  <p class="comment-content">{content}</p>',
        f"  {_render_comment_likes(entry)}",
    ]
    if not is_reply:
        form = _render_reply_form(entry)
        if form:
            lines.append(f"  {form}")
        if replies:
            lines.append(f"  {_render_replies(entry, replies)}")
    lines.append("</li>")
    return "\n".join(lines)


def _render_comments(row) -> str:
    """Render the comment form plus the nested list (or the empty state)."""
    post_id = _escaped(row, "post_id")
    comments = _row_value(row, "comments", None) or []
    if comments:
        tops, replies_by_parent = _split_comments(comments)
        items = "\n".join(
            _render_comment(
                entry,
                replies_by_parent.get(_row_value(entry, "comment_id", None), ()),
            )
            for entry in tops
        )
        listing = f'<ul class="comment-list">\n{items}\n</ul>'
    else:
        listing = '<p class="comments-empty">暂无评论</p>'
    return (
        '<section class="post-comments">\n'
        f'  <form class="comment-form" action="/posts/{post_id}/comments" method="post">\n'
        '    <textarea name="content"></textarea>\n'
        '    <button type="submit">发表评论</button>\n'
        "  </form>\n"
        f"  {listing}\n"
        "</section>"
    )


def _render_post(row) -> str:
    """Render one feed row as an escaped ``<article>`` with interactions."""
    username = _escaped(row, "username")
    created_at = _escaped(row, "created_at")
    content = _escaped(row, "content")
    return (
        '<article class="post">\n'
        f'  <header class="post-author">{username}</header>\n'
        f'  <time class="post-time" datetime="{created_at}">{created_at}</time>\n'
        f'  <p class="post-content">{content}</p>\n'
        f"  {_render_likes(row)}\n"
        f"  {_render_comments(row)}\n"
        "</article>"
    )


def _render_posts(posts) -> str:
    """Render the feed list in the order ``posts`` is given."""
    items = "\n".join(_render_post(post) for post in posts)
    return f'<section id="feed">\n{items}\n</section>'


def feed_page(request) -> Response:
    """Handle ``GET /``: guard, fetch the followed feed, render it or empty."""
    denied = require_login(request)
    if denied is not None:
        return denied

    posts = get_feed(current_user_id(request))
    body = _render_posts(posts) if posts else EMPTY_STATE_HTML
    return html_response(FEED_TITLE, body)


def register(app) -> None:
    """Mount the feed page on ``app`` (``GET /``)."""
    app.route("GET", "/", feed_page)
