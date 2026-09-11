"""FP-005 tests: comment like / unlike entry and liked state.

Scenarios documented in docs/test-cases/fp005-comment-like-ui.md. Render tests
monkeypatch ``views_feed.get_feed`` with contract-shaped stub rows and stub
FP-003's guard, so no database is touched (card §6).
"""

from types import SimpleNamespace

import pytest

from social_app import views_feed
from social_app.app import Request, create_app


def comment_entry(comment_id=1, like_count=0, liked_by_me=False, **overrides):
    """A contract-shaped comment dict (card §3.2)."""
    entry = {
        "comment_id": comment_id,
        "parent_id": None,
        "author": "alice",
        "content": "hi",
        "created_at": "2026-01-01T00:00:00Z",
        "like_count": like_count,
        "liked_by_me": liked_by_me,
    }
    entry.update(overrides)
    return entry


def feed_row(comments, post_id=1):
    """A minimal feed row wrapping ``comments``."""
    return {
        "post_id": post_id,
        "author_id": 9,
        "username": "alice",
        "content": "a post",
        "created_at": "2026-01-01T00:00:00Z",
        "like_count": 0,
        "liked_by_me": False,
        "comments": comments,
    }


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def logged_in(monkeypatch):
    monkeypatch.setattr(views_feed, "require_login", lambda request: None)
    monkeypatch.setattr(views_feed, "current_user_id", lambda request: 7)


def stub_feed(monkeypatch, rows):
    monkeypatch.setattr(views_feed, "get_feed", lambda user_id: rows)


def get_root(app):
    return app.dispatch(Request(method="GET", path="/"))


class TestUnlikedComment:
    """A1–A4: an unliked comment shows count 0 and a like form."""

    def test_unliked_comment_renders_like_form_and_count(
        self, app, logged_in, monkeypatch
    ):
        stub_feed(
            monkeypatch,
            [feed_row([comment_entry(1, like_count=0, liked_by_me=False)])],
        )
        body = get_root(app).body
        assert '<span class="comment-like-count">0</span>' in body
        assert 'class="comment-like-form" action="/comments/1/like"' in body
        assert 'method="post"' in body
        assert "点赞" in body
        assert "/unlike" not in body

    def test_unliked_state_shown(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [feed_row([comment_entry(1)])])
        body = get_root(app).body
        assert '<span class="comment-liked-state">未赞</span>' in body


class TestLikedComment:
    """B1–B4: a liked comment shows count 3 and an unlike form."""

    def test_liked_comment_renders_unlike_form_and_state(
        self, app, logged_in, monkeypatch
    ):
        stub_feed(
            monkeypatch,
            [feed_row([comment_entry(2, like_count=3, liked_by_me=True)])],
        )
        body = get_root(app).body
        assert '<span class="comment-like-count">3</span>' in body
        assert 'class="comment-like-form" action="/comments/2/unlike"' in body
        assert "取消点赞" in body
        assert "/comments/2/like\"" not in body

    def test_liked_state_shown(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [feed_row([comment_entry(2, like_count=3, liked_by_me=True)])],
        )
        body = get_root(app).body
        assert '<span class="comment-liked-state">已赞</span>' in body


class TestDefaultsAndEscaping:
    """C1–C4: missing fields default and all output values are escaped."""

    def test_missing_like_fields_default(self, app, logged_in, monkeypatch):
        legacy_entry = {
            "comment_id": 1,
            "parent_id": None,
            "author": "alice",
            "content": "legacy",
            "created_at": "2026-01-01T00:00:00Z",
        }
        stub_feed(monkeypatch, [feed_row([legacy_entry])])
        response = get_root(app)
        assert response.status == 200
        assert '<span class="comment-like-count">0</span>' in response.body
        assert 'action="/comments/1/like"' in response.body
        assert "未赞" in response.body

    def test_comment_like_control_values_escaped(self):
        html_out = views_feed._render_comment_likes(
            comment_entry(comment_id='1"><script>alert(1)</script>')
        )
        assert "<script>alert(1)</script>" not in html_out
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_out
        assert "&quot;" in html_out

    def test_comment_author_and_content_escaped(self, app, logged_in, monkeypatch):
        entry = comment_entry(
            1,
            author="<b>eve</b>",
            content="<script>alert(1)</script>",
            created_at="<i>t</i>",
        )
        stub_feed(monkeypatch, [feed_row([entry])])
        body = get_root(app).body
        assert "<b>eve</b>" not in body
        assert "<script>alert(1)</script>" not in body
        assert "<i>t</i>" not in body
        assert "&lt;b&gt;eve&lt;/b&gt;" in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    def test_namespace_row_shape_renders(self):
        entry = SimpleNamespace(comment_id=5, like_count=2, liked_by_me=True)
        html_out = views_feed._render_comment_likes(entry)
        assert '<span class="comment-like-count">2</span>' in html_out
        assert 'action="/comments/5/unlike"' in html_out
        assert "取消点赞" in html_out


class TestIntegration:
    """D1–D3: each comment carries its own control; monkeypatch still wins."""

    def test_every_comment_has_its_own_like_control(
        self, app, logged_in, monkeypatch
    ):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(1),
                        comment_entry(2, like_count=3, liked_by_me=True, parent_id=1),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert body.count('class="comment-like-form"') == 2
        assert 'action="/comments/1/like"' in body
        assert 'action="/comments/2/unlike"' in body

    def test_monkeypatched_helper_still_wins(self, app, logged_in, monkeypatch):
        monkeypatch.setattr(
            views_feed,
            "_render_comment_likes",
            lambda entry: '<div class="real-comment-likes">sentinel</div>',
        )
        stub_feed(monkeypatch, [feed_row([comment_entry(1)])])
        body = get_root(app).body
        assert "real-comment-likes" in body
        assert "comment-liked-state" not in body
