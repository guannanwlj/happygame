"""FP-022 tests: feed interaction rendering (social_app.views_feed).

Scenarios documented in docs/test-cases/fp022-feed-render.md. Card §6 isolation:
FP-023's ``get_feed`` is monkeypatched with contract-shaped row stubs (dict /
``SimpleNamespace``) and FP-003's guard is stubbed, so no database is touched.
Requests are dispatched through the app router so a 303 redirect is returned,
not followed.
"""

from types import SimpleNamespace

import pytest

from social_app import views_feed
from social_app.app import Request, create_app


@pytest.fixture()
def app():
    """A fresh app with the real feed route mounted."""
    return create_app()


@pytest.fixture()
def logged_in(monkeypatch):
    """Isolate FP-003: pretend a user with id 7 is logged in."""
    monkeypatch.setattr(views_feed, "require_login", lambda request: None)
    monkeypatch.setattr(views_feed, "current_user_id", lambda request: 7)


def stub_feed(monkeypatch, rows):
    """Replace FP-023 ``get_feed`` with a stub returning ``rows``."""
    monkeypatch.setattr(views_feed, "get_feed", lambda user_id: rows)


def get_root(app):
    """Dispatch ``GET /`` through the app's router."""
    return app.dispatch(Request(method="GET", path="/"))


def comment(author, content, created_at):
    return {"author": author, "content": content, "created_at": created_at}


def interaction_row(**overrides):
    """A full FP-023 contract row; override only what a test cares about."""
    row = {
        "post_id": 1,
        "author_id": 9,
        "username": "bob",
        "content": "first post",
        "created_at": "2026-01-01T00:00:00Z",
        "like_count": 0,
        "liked_by_me": False,
        "comments": [],
    }
    row.update(overrides)
    return row


def liked_row():
    return interaction_row(
        like_count=3,
        liked_by_me=True,
        comments=[
            comment("alice", "older & <b>bold</b>", "2026-01-02T08:00:00Z"),
            comment("carol", "newer", "2026-01-03T09:30:00Z"),
        ],
    )


class TestLikeRendering:
    """A1-A5: like total plus the like / unlike entry point."""

    def test_like_count_and_unlike_form_when_liked(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [liked_row()])
        body = get_root(app).body
        assert '<span class="like-count">3</span>' in body
        assert 'action="/posts/1/unlike"' in body
        assert "取消点赞" in body
        assert 'action="/posts/1/like"' not in body

    def test_like_form_when_not_liked(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [interaction_row(like_count=0, liked_by_me=False)])
        body = get_root(app).body
        assert '<span class="like-count">0</span>' in body
        assert 'action="/posts/1/like"' in body
        assert "点赞" in body
        assert "/unlike" not in body


class TestCommentRendering:
    """B1-B4: comment form and ascending comment list."""

    def test_comments_rendered_ascending_with_author_time(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [liked_row()])
        body = get_root(app).body
        assert body.index("older &amp; &lt;b&gt;bold&lt;/b&gt;") < body.index("newer")
        assert "alice" in body
        assert "carol" in body
        assert "2026-01-02T08:00:00Z" in body
        assert "2026-01-03T09:30:00Z" in body

    def test_comment_form_targets_post(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [liked_row()])
        body = get_root(app).body
        assert 'action="/posts/1/comments"' in body
        assert "<textarea" in body
        assert 'name="content"' in body

    def test_comments_empty_state_keeps_input(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [interaction_row(comments=[])])
        body = get_root(app).body
        assert '<p class="comments-empty">暂无评论</p>' in body
        assert 'action="/posts/1/comments"' in body
        assert "<textarea" in body

    def test_missing_comments_key_uses_empty_state(self, app, logged_in, monkeypatch):
        row = interaction_row()
        del row["comments"]
        stub_feed(monkeypatch, [row])
        body = get_root(app).body
        assert "暂无评论" in body
        assert "<textarea" in body


class TestEscaping:
    """D1-D2: every comment field is HTML-escaped."""

    def test_comment_content_escaped(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [interaction_row(comments=[comment("eve", "<script>alert(1)</script>", "t")])],
        )
        body = get_root(app).body
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    def test_comment_author_and_time_escaped(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [interaction_row(comments=[comment("<b>eve</b>", "hi", "<i>t</i>")])],
        )
        body = get_root(app).body
        assert "<b>eve</b>" not in body
        assert "<i>t</i>" not in body
        assert "&lt;b&gt;eve&lt;/b&gt;" in body
        assert "&lt;i&gt;t&lt;/i&gt;" in body


class TestRowShapes:
    """E1-E3: legacy rows and namespace rows still render."""

    def test_legacy_row_stub_still_renders(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [{"username": "bob", "content": "legacy", "created_at": "2026-01-01T00:00:00Z"}],
        )
        response = get_root(app)
        assert response.status == 200
        assert "legacy" in response.body
        assert "bob" in response.body

    def test_legacy_row_defaults_like_and_comments(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [{"username": "bob", "content": "legacy", "created_at": "2026-01-01T00:00:00Z"}],
        )
        body = get_root(app).body
        assert '<span class="like-count">0</span>' in body
        assert "点赞" in body
        assert "暂无评论" in body

    def test_namespace_contract_row_renders(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                SimpleNamespace(
                    post_id=5,
                    author_id=2,
                    username="bob",
                    content="hello",
                    created_at="2026-01-01T00:00:00Z",
                    like_count=1,
                    liked_by_me=True,
                    comments=[
                        SimpleNamespace(
                            author="alice", content="nice", created_at="2026-01-02T00:00:00Z"
                        )
                    ],
                )
            ],
        )
        body = get_root(app).body
        assert 'action="/posts/5/unlike"' in body
        assert "nice" in body
        assert "alice" in body
