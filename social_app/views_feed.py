"""Feed page and empty state (FP-014).

Makes ``GET /`` the home feed: guard the request through FP-003
(:mod:`social_app.session`), fetch the followed users' posts through FP-005
(:mod:`social_app.feed`) and render them newest-first. With no posts the page
shows an empty-state guide, and anonymous visitors are sent to ``/login``.

FP-022 extends the per-post rendering with the interaction layer: the like
total, the viewer's like/unlike form (from the FP-023 row's ``like_count`` /
``liked_by_me``) and the comment form plus list (``comments``). The forms point
at the FP-020/FP-021 routes; this module only renders them.

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


def _render_comment(entry) -> str:
    """Render one comment as an escaped ``<li>``."""
    author = _escaped(entry, "author")
    created_at = _escaped(entry, "created_at")
    content = _escaped(entry, "content")
    return (
        '<li class="comment">\n'
        f'  <span class="comment-author">{author}</span>\n'
        f'  <time class="comment-time" datetime="{created_at}">{created_at}</time>\n'
        f'  <p class="comment-content">{content}</p>\n'
        "</li>"
    )


def _render_comments(row) -> str:
    """Render the comment form plus the list (or the empty state)."""
    post_id = _escaped(row, "post_id")
    comments = _row_value(row, "comments", None) or []
    if comments:
        items = "\n".join(_render_comment(entry) for entry in comments)
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
