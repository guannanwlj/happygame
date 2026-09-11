"""FP-021 tests: comment submit route (social_app.views_comment).

Scenarios documented in docs/test-cases/fp021-comment-routes.md. Requests are
dispatched in-process (``create_app().dispatch`` / direct handler calls), never
over the network. Per card §6 the FP-003 login guard, FP-019 authorization and
FP-018 comment service are isolated by monkeypatching the module-level names in
``views_comment``; one extra test runs the landed services against a fresh
temporary DB.
"""

from urllib.parse import urlencode

import pytest

from social_app import db
from social_app import session
from social_app import views_comment
from social_app.app import Request, SocialApp, create_app, redirect

ACTOR_ID = 7
POST_ID = 1
COMMENT_PATH = f"/posts/{POST_ID}/comments"
BLANK_MESSAGE = "评论内容不能为空"
FORBIDDEN_MESSAGE = "无权互动该帖子"


class CommentRecorder:
    """Records calls and mimics the FP-018 service: fail or write."""

    def __init__(self):
        self.calls = []
        self.writes = []
        self.fail_with = None

    def __call__(self, post_id, author_id, content):
        self.calls.append((post_id, author_id, content))
        if self.fail_with is not None:
            raise views_comment.CommentError(self.fail_with)
        self.writes.append((post_id, author_id, content))
        return len(self.writes)


class AuthorizeRecorder:
    """Records calls and mimics the FP-019 guard: pass or deny."""

    def __init__(self):
        self.calls = []
        self.fail_with = None

    def __call__(self, actor_id, post_id):
        self.calls.append((actor_id, post_id))
        if self.fail_with is not None:
            raise views_comment.InteractionError(self.fail_with)


@pytest.fixture(autouse=True)
def clean_sessions():
    """Isolate every test from the process-wide session store (FP-003)."""
    with session._lock:
        session._sessions.clear()
    yield
    with session._lock:
        session._sessions.clear()


@pytest.fixture
def logged_in(monkeypatch):
    """Card §6 mock: treat every request as user ``ACTOR_ID``."""
    monkeypatch.setattr(views_comment, "require_login", lambda request: None)
    monkeypatch.setattr(views_comment, "current_user_id", lambda _request: ACTOR_ID)
    return ACTOR_ID


@pytest.fixture
def authorize(monkeypatch):
    """Card §6 mock: an allowing ``authorize_interaction`` recorder."""
    recorder = AuthorizeRecorder()
    monkeypatch.setattr(views_comment, "authorize_interaction", recorder)
    return recorder


@pytest.fixture
def comments(monkeypatch):
    """Card §6 mock: an ``add_comment`` recorder (success unless told to fail)."""
    recorder = CommentRecorder()
    monkeypatch.setattr(views_comment, "add_comment", recorder)
    return recorder


def post_request(path=COMMENT_PATH, body=b"content=hi", params=None, cookies=None):
    return Request(
        method="POST",
        path=path,
        params=params if params is not None else {"id": str(POST_ID)},
        body=body,
        cookies=cookies or {},
    )


def form_body(**fields) -> bytes:
    return urlencode(fields).encode("utf-8")


class TestSuccessfulSubmit:
    """A1–A5: a logged-in actor's valid submit saves and redirects home."""

    def test_comment_logged_in_saves_and_redirects_home(
        self, logged_in, authorize, comments
    ):
        response = views_comment.comment_submit(
            post_request(body=form_body(content="你好"))
        )
        assert response.status == 303
        assert response.headers["Location"] == "/"

    def test_calls_add_comment_with_post_actor_and_content(
        self, logged_in, authorize, comments
    ):
        views_comment.comment_submit(post_request(body=form_body(content="你好")))
        assert comments.calls == [(POST_ID, ACTOR_ID, "你好")]

    def test_percent_encoding_is_decoded(self, logged_in, authorize, comments):
        views_comment.comment_submit(
            post_request(body=b"content=hello+world")
        )
        assert comments.calls == [(POST_ID, ACTOR_ID, "hello world")]

    def test_missing_content_field_is_blank(self, logged_in, authorize, comments):
        views_comment.comment_submit(post_request(body=b"other=x"))
        assert comments.calls == [(POST_ID, ACTOR_ID, "")]

    def test_authorize_precedes_add(self, logged_in, authorize, comments):
        views_comment.comment_submit(post_request(body=form_body(content="hi")))
        assert authorize.calls == [(ACTOR_ID, POST_ID)]


class TestBlankContent:
    """B1–B3: a CommentError renders a readable page and no successful write."""

    def test_blank_content_returns_readable_error_and_no_write(
        self, logged_in, authorize, comments
    ):
        comments.fail_with = BLANK_MESSAGE
        response = views_comment.comment_submit(
            post_request(body=form_body(content="   "))
        )
        assert response.status == 200
        assert BLANK_MESSAGE in response.body
        assert '<a href="/">' in response.body
        assert comments.writes == []

    def test_comment_error_does_not_redirect(self, logged_in, authorize, comments):
        comments.fail_with = BLANK_MESSAGE
        response = views_comment.comment_submit(
            post_request(body=form_body(content=""))
        )
        assert "Location" not in response.headers

    def test_comment_error_message_is_escaped(
        self, logged_in, authorize, comments
    ):
        comments.fail_with = "<b>坏</b>"
        response = views_comment.comment_submit(
            post_request(body=form_body(content="x"))
        )
        assert "<b>坏</b>" not in response.body
        assert "&lt;b&gt;坏&lt;/b&gt;" in response.body


class TestAnonymousRequest:
    """C1–C3: the login guard short-circuits before any service call."""

    def test_anonymous_redirects_login_and_no_write(self, authorize, comments):
        response = create_app().dispatch(
            post_request(body=form_body(content="hi"))
        )
        assert response.status == 303
        assert response.headers["Location"] == "/login"
        assert comments.calls == []
        assert authorize.calls == []

    def test_guard_response_is_returned_unchanged(
        self, monkeypatch, authorize, comments
    ):
        guard = redirect("/login")
        monkeypatch.setattr(views_comment, "require_login", lambda request: guard)
        response = views_comment.comment_submit(
            post_request(body=form_body(content="hi"))
        )
        assert response is guard
        assert comments.calls == []
        assert authorize.calls == []


class TestUnauthorizedRequest:
    """D1–D3: an InteractionError renders a readable page and never writes."""

    def test_unauthorized_returns_readable_error_and_no_write(
        self, logged_in, authorize, comments
    ):
        authorize.fail_with = FORBIDDEN_MESSAGE
        response = views_comment.comment_submit(
            post_request(body=form_body(content="hi"))
        )
        assert response.status == 200
        assert FORBIDDEN_MESSAGE in response.body
        assert '<a href="/">' in response.body
        assert comments.calls == []

    def test_interaction_error_message_is_escaped(
        self, logged_in, authorize, comments
    ):
        authorize.fail_with = "<b>bad</b>"
        response = views_comment.comment_submit(
            post_request(body=form_body(content="hi"))
        )
        assert "<b>bad</b>" not in response.body
        assert "&lt;b&gt;bad&lt;/b&gt;" in response.body


class TestRouting:
    """E1–E4: the route is mounted and dispatchable on the real app."""

    def test_route_mounted_in_create_app(self):
        routes = {(route.method, route.pattern) for route in create_app().routes}
        assert ("POST", "/posts/<id>/comments") in routes

    def test_register_mounts_handler_on_bare_app(self, logged_in, authorize, comments):
        app = SocialApp()
        views_comment.register(app)
        response = app.dispatch(post_request(body=form_body(content="hi")))
        assert response.status == 303
        assert response.headers["Location"] == "/"

    def test_get_is_method_not_allowed(self):
        response = create_app().dispatch(
            Request(method="GET", path=COMMENT_PATH)
        )
        assert response.status == 405
        assert "POST" in response.headers["Allow"]

    def test_submit_reaches_handler_not_placeholder(
        self, logged_in, authorize, comments
    ):
        response = create_app().dispatch(post_request(body=form_body(content="hi")))
        assert response.status != 501
        assert "501" not in response.body


class TestPathParams:
    """F1–F2: the ``<id>`` path segment reaches the service as an int."""

    @pytest.mark.parametrize("post_id", [1, 42, 999])
    def test_path_id_is_parsed_as_int(
        self, logged_in, authorize, comments, post_id
    ):
        path = f"/posts/{post_id}/comments"
        views_comment.comment_submit(
            post_request(path=path, params={"id": str(post_id)}, body=b"content=hi")
        )
        assert comments.calls == [(post_id, ACTOR_ID, "hi")]


class TestRealServicesIntegration:
    """A6: the landed FP-018/FP-019 services work through the route."""

    def test_writes_comment_with_real_services(self, tmp_path, monkeypatch):
        monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "social.db"))
        db.init_db()
        cur = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("alice", "hash"),
        )
        alice = cur.lastrowid
        cur = db.execute(
            "INSERT INTO posts (author_id, content) VALUES (?, ?)",
            (alice, "post"),
        )
        post_id = cur.lastrowid
        token = session.create_session(alice)

        request = Request(
            method="POST",
            path=f"/posts/{post_id}/comments",
            body=form_body(content="你好"),
            cookies={session.SESSION_COOKIE: token},
        )
        response = create_app().dispatch(request)

        assert response.status == 303
        assert response.headers["Location"] == "/"
        rows = db.query_all(
            "SELECT author_id, content FROM comments WHERE post_id = ?",
            (post_id,),
        )
        assert [(r["author_id"], r["content"]) for r in rows] == [(alice, "你好")]
