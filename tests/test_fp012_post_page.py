"""FP-012 tests: post page / submit orchestration (social_app.views_post).

Scenarios documented in docs/test-cases/fp012-post-page.md. Requests are
dispatched in-process (``SocialApp.dispatch`` / direct handler calls), never
over the network. Per card §6, FP-013 is isolated by monkeypatching
``social_app.posts.create_post``; if FP-013 is absent from the checkout a stub
module is registered so the lazy import in ``views_post`` resolves.
"""

import sys
import types
from types import SimpleNamespace

import pytest

from social_app import session
from social_app import views_post
from social_app.app import Request, SocialApp, create_app, redirect


def _posts_module():
    """Return ``social_app.posts``, registering a stub when FP-013 is absent."""
    try:
        from social_app import posts as module
    except ImportError:
        import social_app

        module = types.ModuleType("social_app.posts")

        class PostError(Exception):
            """Local stand-in for the FP-013 error type."""

        module.PostError = PostError
        module.create_post = lambda author_id, content: 0
        sys.modules["social_app.posts"] = module
        social_app.posts = module
    return module


class PostsRecorder:
    """Records calls and mimics the FP-013 validation contract."""

    def __init__(self, module):
        self.module = module
        self.calls = []

    def create_post(self, author_id, content):
        self.calls.append((author_id, content))
        if author_id is None:
            raise self.module.PostError("未登录")
        if content.strip() == "":
            raise self.module.PostError("内容不能为空")
        return len(self.calls)


@pytest.fixture(autouse=True)
def clean_sessions():
    """Isolate every test from the process-wide session store (FP-003)."""
    with session._lock:
        session._sessions.clear()
    yield
    with session._lock:
        session._sessions.clear()


@pytest.fixture
def posts(monkeypatch):
    """Card §6 mock: a recording ``create_post`` on the posts module."""
    recorder = PostsRecorder(_posts_module())
    monkeypatch.setattr(recorder.module, "create_post", recorder.create_post)
    return recorder


@pytest.fixture
def logged_in(monkeypatch):
    """Card §6 mock: treat every request as user 7."""
    monkeypatch.setattr(views_post, "require_login", lambda request: None)
    monkeypatch.setattr(views_post, "current_user_id", lambda request: 7)


def request(method="GET", path="/posts/new", body=b"", cookies=None):
    return Request(
        method=method, path=path, body=body, cookies=cookies or {}
    )


class TestFormPage:
    """A1–A3: GET /posts/new."""

    def test_logged_in_renders_textarea(self, logged_in):
        response = views_post.post_form(request())
        assert response.status == 200
        assert response.content_type.startswith("text/html")
        assert "<textarea" in response.body
        assert 'name="content"' in response.body

    def test_form_submits_to_posts(self, logged_in):
        body = views_post.post_form(request()).body
        assert 'action="/posts"' in body
        assert 'method="post"' in body

    def test_anonymous_redirects_to_login(self):
        response = views_post.post_form(request())
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_anonymous_body_is_not_a_form(self):
        body = views_post.post_form(request()).body
        assert "<textarea" not in body


class TestSuccessfulSubmit:
    """B1–B4: POST /posts with non-empty content."""

    def test_redirects_to_feed(self, logged_in, posts):
        response = views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=hello")
        )
        assert response.status == 303
        assert response.headers["Location"] == "/"

    def test_calls_create_post_once_with_author_and_text(self, logged_in, posts):
        views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=hello")
        )
        assert posts.calls == [(7, "hello")]

    def test_percent_encoding_is_decoded(self, logged_in, posts):
        views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=hello+world")
        )
        assert posts.calls == [(7, "hello world")]

    def test_uses_real_session_user(self, monkeypatch, posts):
        monkeypatch.setattr(views_post, "require_login", lambda request: None)
        token = session.create_session(7)
        response = views_post.post_submit(
            request(
                method="POST",
                path="/posts",
                body=b"content=hi",
                cookies={session.SESSION_COOKIE: token},
            )
        )
        assert response.status == 303
        assert posts.calls == [(7, "hi")]


class TestEmptyContent:
    """C1–C4: rejected content re-renders the form with an error."""

    @pytest.mark.parametrize(
        "body", [b"content=%20%20", b"content=", b"other=x"]
    )
    def test_shows_cannot_be_empty(self, logged_in, posts, body):
        response = views_post.post_submit(
            request(method="POST", path="/posts", body=body)
        )
        assert response.status == 200
        assert "不能为空" in response.body

    def test_error_page_keeps_form(self, logged_in, posts):
        body = views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=%20")
        ).body
        assert "<textarea" in body
        assert 'name="content"' in body

    def test_error_page_does_not_redirect(self, logged_in, posts):
        response = views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=")
        )
        assert "Location" not in response.headers


class TestAnonymousSubmit:
    """D1–D2: the login guard runs before any write."""

    def test_post_redirects_and_skips_write(self, posts):
        response = views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=hi")
        )
        assert response.status == 303
        assert response.headers["Location"] == "/login"
        assert posts.calls == []

    def test_get_redirects(self):
        response = views_post.post_form(request())
        assert response.status == 303


class TestGuardDelegation:
    """E1: a guard response is returned unchanged, no write happens."""

    def test_guard_response_passed_through(self, monkeypatch, posts):
        guard = redirect("/login")
        monkeypatch.setattr(views_post, "require_login", lambda request: guard)
        response = views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=hi")
        )
        assert response is guard
        assert posts.calls == []


class TestRouting:
    """E2–E4: app wiring replaces the FP-012 placeholders."""

    def test_create_app_get_form_uses_guard_not_placeholder(self):
        response = create_app().dispatch(request())
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_register_mounts_both_routes(self, logged_in, posts):
        app = SocialApp()
        views_post.register(app)
        form = app.dispatch(request())
        submit = app.dispatch(
            request(method="POST", path="/posts", body=b"content=hi")
        )
        assert form.status == 200
        assert submit.status == 303
        assert posts.calls == [(7, "hi")]

    def test_get_posts_still_method_not_allowed(self):
        response = create_app().dispatch(
            Request(method="GET", path="/posts")
        )
        assert response.status == 405
        assert "POST" in response.headers["Allow"]


class TestEscaping:
    """F1: rejected content is escaped when echoed back."""

    def test_malicious_content_is_escaped(self, logged_in, posts, monkeypatch):
        module = posts.module

        def boom(author_id, content):
            posts.calls.append((author_id, content))
            raise module.PostError("内容不能为空")

        monkeypatch.setattr(module, "create_post", boom)
        response = views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=<script>")
        )
        assert "&lt;script&gt;" in response.body
        assert "<script>" not in response.body

    def test_error_message_is_escaped(self, monkeypatch, posts):
        module = posts.module

        def boom(author_id, content):
            raise module.PostError("<b>bad</b>")

        monkeypatch.setattr(module, "create_post", boom)
        monkeypatch.setattr(views_post, "require_login", lambda request: None)
        response = views_post.post_submit(
            request(method="POST", path="/posts", body=b"content=hi")
        )
        assert "&lt;b&gt;bad&lt;/b&gt;" in response.body
        assert "<b>bad</b>" not in response.body
