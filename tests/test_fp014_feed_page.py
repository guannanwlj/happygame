"""FP-014 tests: feed page and empty state (social_app.views_feed).

Scenarios documented in docs/test-cases/fp014-feed-page.md. Card §6 isolation:
FP-005's ``get_feed`` is monkeypatched (dict / ``SimpleNamespace`` rows) and
FP-003's guard is exercised with the real session module as well as a stub.
Requests are dispatched directly so a 303 redirect is returned, not followed.
"""

from types import SimpleNamespace

import pytest

from social_app import session
from social_app import views_feed
from social_app.app import Request, create_app, redirect


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
    """Replace FP-005 ``get_feed`` with a stub returning ``rows``."""
    monkeypatch.setattr(views_feed, "get_feed", lambda user_id: rows)


def get_root(app):
    """Dispatch ``GET /`` through the app's router."""
    return app.dispatch(Request(method="GET", path="/"))


def post_row(username="bob", content="first", created_at="2026-01-01T00:00:00Z"):
    return {"username": username, "content": content, "created_at": created_at}


class TestFeedRendering:
    """A1–A3: a logged-in user sees the returned posts newest-first."""

    def test_renders_posts_as_html(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [post_row()])
        response = get_root(app)
        assert response.status == 200
        assert response.content_type.startswith("text/html")
        assert "<!DOCTYPE html>" in response.body
        assert "first" in response.body
        assert "bob" in response.body
        assert "2026-01-01T00:00:00Z" in response.body

    def test_preserves_get_feed_order(self, app, logged_in, monkeypatch):
        rows = [
            post_row(content="newer", created_at="2026-01-02T00:00:00Z"),
            post_row(username="carol", content="older", created_at="2026-01-01T00:00:00Z"),
        ]
        stub_feed(monkeypatch, rows)
        body = get_root(app).body
        assert body.index("newer") < body.index("older")

    def test_get_feed_receives_logged_in_id(self, app, logged_in, monkeypatch):
        seen = []
        monkeypatch.setattr(views_feed, "get_feed", lambda user_id: seen.append(user_id) or [])
        get_root(app)
        assert seen == [7]


class TestEmptyState:
    """B1–B2: no posts renders the follow/publish guidance."""

    def test_empty_feed_renders_empty_state(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [])
        response = get_root(app)
        assert response.status == 200
        assert 'id="feed-empty"' in response.body

    def test_empty_state_guides_user(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [])
        body = get_root(app).body
        assert "关注" in body
        assert "发帖" in body
        assert 'href="/posts/new"' in body


class TestLoginGuard:
    """C1–C3: anonymous visitors never reach the feed query."""

    def test_anonymous_redirects_to_login(self, app, monkeypatch):
        seen = []
        monkeypatch.setattr(views_feed, "get_feed", lambda user_id: seen.append(user_id))
        response = get_root(app)
        assert response.status == 303
        assert response.headers["Location"] == "/login"
        assert seen == []

    def test_guard_response_returned_unmodified(self, app, monkeypatch):
        sentinel = redirect("/login")
        monkeypatch.setattr(views_feed, "require_login", lambda request: sentinel)
        monkeypatch.setattr(
            views_feed, "current_user_id", lambda request: pytest.fail("must not run")
        )
        response = get_root(app)
        assert response is sentinel

    def test_real_session_identity_is_used(self, app, monkeypatch):
        token = session.create_session(42)
        captured = []
        monkeypatch.setattr(
            views_feed, "get_feed", lambda user_id: captured.append(user_id) or []
        )
        request = Request(method="GET", path="/", cookies={"session": token})
        assert app.dispatch(request).status == 200
        assert captured == [42]


class TestEscaping:
    """D1–D3: all rendered values are HTML-escaped."""

    def test_content_script_is_escaped(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [post_row(content="<script>alert(1)</script>")])
        body = get_root(app).body
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    def test_content_quotes_and_ampersand_escaped(self, app, logged_in, monkeypatch):
        stub_feed(monkeypatch, [post_row(content='5 < 6 & "q" \'s\'')])
        body = get_root(app).body
        assert "&amp;" in body
        assert "&lt;" in body
        assert "&quot;" in body
        assert "&#x27;" in body

    def test_username_and_timestamp_escaped(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [post_row(username="<b>bob</b>", created_at="<i>t</i>")],
        )
        body = get_root(app).body
        assert "<b>bob</b>" not in body
        assert "<i>t</i>" not in body
        assert "&lt;b&gt;bob&lt;/b&gt;" in body


class TestRowShapes:
    """E1–E2: key rows and attribute rows both render (card §6)."""

    @pytest.mark.parametrize(
        "make_row",
        [lambda **kw: kw, lambda **kw: SimpleNamespace(**kw)],
        ids=["dict", "namespace"],
    )
    def test_supported_row_shapes(self, app, logged_in, monkeypatch, make_row):
        stub_feed(monkeypatch, [make_row(**post_row(content="hello"))])
        body = get_root(app).body
        assert "hello" in body
        assert "bob" in body


class TestMounting:
    """E3, F1: GET / is the real feed page, not the FP-001 placeholder."""

    def test_get_root_maps_to_feed_page(self):
        routes = {(route.method, route.pattern): route.handler for route in create_app().routes}
        assert routes[("GET", "/")] is views_feed.feed_page

    def test_root_is_no_longer_placeholder(self, app):
        response = get_root(app)
        assert response.status == 303
        assert "占位" not in response.body
