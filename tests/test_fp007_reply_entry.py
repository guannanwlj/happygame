"""FP-007 tests: reply entry point under top-level comments.

Scenarios documented in docs/test-cases/fp007-reply-entry.md. Rendering only:
each test monkeypatches ``views_feed.get_feed`` with contract-shaped stub rows
and stubs FP-003's guard, then dispatches ``GET /`` through ``create_app()``
(card §6). No database is touched, so FP-002/FP-004/FP-009 are not required.
"""

from types import SimpleNamespace

import pytest

from social_app import views_feed
from social_app.app import Request, create_app


def comment_entry(
    comment_id,
    parent_id,
    author,
    content,
    created_at,
    like_count=0,
    liked_by_me=False,
):
    """Build one FP-009 contract comment dict (card §3.2)."""
    return {
        "comment_id": comment_id,
        "parent_id": parent_id,
        "author": author,
        "content": content,
        "created_at": created_at,
        "like_count": like_count,
        "liked_by_me": liked_by_me,
    }


def feed_row(comments, post_id=1):
    """Build one feed row carrying ``comments``."""
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


def top_comment():
    return comment_entry(1, None, "alice", "top", "2026-01-01T00:00:00Z")


def reply(comment_id, content, created_at):
    return comment_entry(comment_id, 1, "bob", content, created_at)


class TestReplyForm:
    """Acceptance 1: the top-level comment exposes the FP-004 reply form."""

    def test_top_level_comment_renders_reply_form(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [feed_row([top_comment()])])
        body = get_root(app).body
        assert 'class="reply-form"' in body
        assert 'action="/comments/1/replies"' in body
        assert 'method="post"' in body

    def test_reply_form_has_content_field_and_button(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [feed_row([top_comment()])])
        body = get_root(app).body
        assert '<textarea name="content"></textarea>' in body
        assert "<button type=\"submit\">回复</button>" in body

    def test_reply_form_renders_without_existing_replies(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [feed_row([top_comment()])])
        body = get_root(app).body
        assert 'action="/comments/1/replies"' in body
        assert '<ul class="reply-list">' not in body


class TestRepliesNestedAscending:
    """Acceptance 2: replies nest one level under the parent, in caller order."""

    def test_replies_nested_under_parent_ascending(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        top_comment(),
                        reply(2, "older", "2026-01-01T01:00:00Z"),
                        reply(3, "newer", "2026-01-01T02:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert '<ul class="reply-list">' in body
        assert body.index("top") < body.index("older") < body.index("newer")
        assert body.count('<ul class="reply-list">') == 1

    def test_each_parent_gets_its_own_reply_list(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(1, None, "alice", "first parent", "t1"),
                        comment_entry(2, None, "carol", "second parent", "t2"),
                        reply(3, "r-for-first", "2026-01-01T01:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert body.count('<ul class="reply-list">') == 1
        assert 'action="/comments/1/replies"' in body
        assert 'action="/comments/2/replies"' in body


class TestOneLevelOnly:
    """Acceptance 3: a reply never carries its own reply entry point."""

    def test_reply_has_no_nested_reply_form(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        top_comment(),
                        reply(2, "older", "2026-01-01T01:00:00Z"),
                        reply(3, "newer", "2026-01-01T02:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert 'action="/comments/2/replies"' not in body
        assert 'action="/comments/3/replies"' not in body
        assert body.count('class="reply-form"') == 1
        assert body.count('<ul class="reply-list">') == 1


class TestEscaping:
    """Acceptance 4: every reply field is HTML-escaped."""

    def test_reply_content_escaped(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        top_comment(),
                        reply(2, "<script>alert(1)</script>", "t1"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    def test_reply_author_and_time_escaped(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        top_comment(),
                        comment_entry(2, 1, "<b>eve</b>", "hi", "<i>t</i>"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert "<b>eve</b>" not in body
        assert "<i>t</i>" not in body
        assert "&lt;b&gt;eve&lt;/b&gt;" in body
        assert "&lt;i&gt;t&lt;/i&gt;" in body

    def test_namespace_contract_row_renders_reply_form(self, app, logged_in, monkeypatch):
        row = SimpleNamespace(
            post_id=5,
            author_id=1,
            username="alice",
            content="post",
            created_at="2026-01-01T00:00:00Z",
            like_count=0,
            liked_by_me=False,
            comments=[
                SimpleNamespace(
                    comment_id=7,
                    parent_id=None,
                    author="alice",
                    content="nice",
                    created_at="2026-01-02T00:00:00Z",
                    like_count=0,
                    liked_by_me=False,
                )
            ],
        )
        stub_feed(monkeypatch, [row])
        body = get_root(app).body
        assert 'action="/comments/7/replies"' in body


class TestCompatibility:
    """Edge cases: legacy shapes and monkeypatched sibling helpers."""

    def test_legacy_comment_dict_still_renders(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        {
                            "author": "eve",
                            "content": "old comment",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                )
            ],
        )
        response = get_root(app)
        assert response.status == 200
        assert "old comment" in response.body
        assert 'class="reply-form"' in response.body

    def test_monkeypatched_reply_helpers_win(self, app, logged_in, monkeypatch):
        monkeypatch.setattr(
            views_feed, "_render_reply_form", lambda entry: '<form id="stub-reply"></form>'
        )
        monkeypatch.setattr(
            views_feed,
            "_render_replies",
            lambda entry, replies: '<ul class="stub-replies"></ul>',
        )
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        top_comment(),
                        reply(2, "older", "2026-01-01T01:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert 'id="stub-reply"' in body
        assert "stub-replies" in body
        assert "reply-list" not in body
