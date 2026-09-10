"""Feed page and empty state (FP-014).

Makes ``GET /`` the home feed: guard the request through FP-003
(:mod:`social_app.session`), fetch the followed users' posts through FP-005
(:mod:`social_app.feed`) and render them newest-first. With no posts the page
shows an empty-state guide, and anonymous visitors are sent to ``/login``.

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


def _row_value(row, key: str) -> str:
    """Read ``key`` from a ``sqlite3.Row``/``dict`` or a mock namespace."""
    try:
        value = row[key]
    except (TypeError, KeyError, IndexError):
        value = getattr(row, key)
    return str(value)


def _render_post(row) -> str:
    """Render one feed row as an escaped ``<article>``."""
    username = html.escape(_row_value(row, "username"))
    created_at = html.escape(_row_value(row, "created_at"))
    content = html.escape(_row_value(row, "content"))
    return (
        '<article class="post">\n'
        f'  <header class="post-author">{username}</header>\n'
        f'  <time class="post-time" datetime="{created_at}">{created_at}</time>\n'
        f'  <p class="post-content">{content}</p>\n'
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
