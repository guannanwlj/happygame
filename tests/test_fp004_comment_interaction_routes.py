"""FP-004 tests: comment interaction submit routes.

Scenarios documented in docs/test-cases/fp004-comment-interaction-routes.md.
Requests are dispatched in-process (``create_app().dispatch`` / direct handler
calls), never over the network and never following redirects. Per card §6 the
FP-003 session/authorization and the FP-006/FP-008 services are isolated by
monkeypatching the module-level names in ``views_comment_interaction``.
"""

from urllib.parse import urlencode

import pytest

from social_app import db
from social_app import session
from social_app import views_comment_interaction as views
from social_app.app import Request, SocialApp, create_app, redirect

ACTOR_ID = 7
COMMENT_ID = 1
LIKE_PATH = f"/comments/{COMMENT_ID}/like"
UNLIKE_PATH = f"/comments/{COMMENT_ID}/unlike"
REPLY_PATH = f"/comments/{COMMENT_ID}/replies"
DENIED_MESSAGE = "评论不存在"
REPLY_ERROR_MESSAGE = "回复内容不能为空"


def form_body(**fields) -> bytes:
    return urlencode(fields).encode("utf-8")


def post_request(path, body=b"", params=None, cookies=None):
    return Request(
        method="POST",
        path=path,
        params=params if params is not None else {"id": str(COMMENT_ID)},
        body=body,
        cookies=cookies or {},
    )


def _forbidden(label):
    def boom(*args, **kwargs):
        raise AssertionError(f"{label} must not run")

    return boom


class AuthorizeRecorder:
    """Records calls and mimics the FP-003 comment guard: pass or deny."""

    def __init__(self):
        self.calls = []
        self.fail_with = None

    def __call__(self, actor_id, comment_id):
        self.calls.append((actor_id, comment_id))
        if self.fail_with is not None:
            raise views.InteractionError(self.fail_with)


class LikeRecorder:
    """Records calls and mimics the FP-006 like service: always succeeds."""

    def __init__(self):
        self.calls = []

    def __call__(self, actor_id, comment_id):
        self.calls.append((actor_id, comment_id))
        return 1


class ReplyRecorder:
    """Records calls and mimics the FP-008 reply service: fail or write."""

    def __init__(self):
        self.calls = []
        self.writes = []
        self.fail_with = None

    def __call__(self, parent_id, author_id, content):
        self.calls.append((parent_id, author_id, content))
        if self.fail_with is not None:
            raise views.ReplyError(self.fail_with)
        self.writes.append((parent_id, author_id, content))
        return len(self.writes)


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
    monkeypatch.setattr(views, "require_login", lambda request: None)
    monkeypatch.setattr(views, "current_user_id", lambda _request: ACTOR_ID)


@pytest.fixture
def anonymous(monkeypatch):
    """Card §6 mock: the guard returns the login redirect."""
    monkeypatch.setattr(
        views, "require_login", lambda request: redirect("/login")
    )
    monkeypatch.setattr(views, "current_user_id", lambda _request: None)


@pytest.fixture
def authorize(monkeypatch):
    """Card §6 mock: an allowing ``authorize_comment_interaction`` recorder."""
    recorder = AuthorizeRecorder()
    monkeypatch.setattr(views, "authorize_comment_interaction", recorder)
    return recorder


@pytest.fixture
def like(monkeypatch):
    """Card §6 mock: a ``like_comment`` recorder (success)."""
    recorder = LikeRecorder()
    monkeypatch.setattr(views, "like_comment", recorder)
    return recorder


@pytest.fixture
def unlike(monkeypatch):
    """Card §6 mock: a ``unlike_comment`` recorder (success)."""
    recorder = LikeRecorder()
    monkeypatch.setattr(views, "unlike_comment", recorder)
    return recorder


@pytest.fixture
def reply(monkeypatch):
    """Card §6 mock: an ``add_reply`` recorder (success unless told to fail)."""
    recorder = ReplyRecorder()
    monkeypatch.setattr(views, "add_reply", recorder)
    return recorder


class TestLikeSubmit:
    """A1–A4: a logged-in, authorized like redirects home and calls the service."""

    def test_like_submit_redirects_home(self, logged_in, authorize, like):
        response = create_app().dispatch(post_request(LIKE_PATH))
        assert response.status == 303
        assert response.headers["Location"] == "/"

    def test_like_service_called_with_actor_and_comment(
        self, logged_in, authorize, like
    ):
        create_app().dispatch(post_request(LIKE_PATH))
        assert like.calls == [(ACTOR_ID, COMMENT_ID)]

    def test_like_does_not_call_unlike(self, logged_in, authorize, like, unlike):
        create_app().dispatch(post_request(LIKE_PATH))
        assert unlike.calls == []

    def test_authorize_precedes_like(self, logged_in, authorize, like):
        create_app().dispatch(post_request(LIKE_PATH))
        assert authorize.calls == [(ACTOR_ID, COMMENT_ID)]


class TestUnlikeSubmit:
    """B1–B2: a logged-in, authorized unlike redirects home and calls the service."""

    def test_unlike_submit_redirects_home(self, logged_in, authorize, unlike):
        response = create_app().dispatch(post_request(UNLIKE_PATH))
        assert response.status == 303
        assert response.headers["Location"] == "/"

    def test_unlike_service_called_and_like_untouched(
        self, logged_in, authorize, like, unlike
    ):
        create_app().dispatch(post_request(UNLIKE_PATH))
        assert unlike.calls == [(ACTOR_ID, COMMENT_ID)]
        assert like.calls == []


class TestReplySubmit:
    """C1–C4: a logged-in, authorized reply redirects home and calls the service."""

    def test_reply_submit_redirects_home(self, logged_in, authorize, reply):
        response = create_app().dispatch(
            post_request(REPLY_PATH, body=form_body(content="hi"))
        )
        assert response.status == 303
        assert response.headers["Location"] == "/"

    def test_reply_service_called_with_parent_actor_and_content(
        self, logged_in, authorize, reply
    ):
        create_app().dispatch(
            post_request(REPLY_PATH, body=form_body(content="hi"))
        )
        assert reply.calls == [(COMMENT_ID, ACTOR_ID, "hi")]

    def test_percent_encoding_is_decoded(self, logged_in, authorize, reply):
        create_app().dispatch(
            post_request(REPLY_PATH, body=b"content=hello+world")
        )
        assert reply.calls == [(COMMENT_ID, ACTOR_ID, "hello world")]

    def test_missing_content_field_is_blank(self, logged_in, authorize, reply):
        create_app().dispatch(post_request(REPLY_PATH, body=b"other=x"))
        assert reply.calls == [(COMMENT_ID, ACTOR_ID, "")]


class TestAnonymousRequest:
    """D1–D3: the login guard short-circuits before any service call."""

    @pytest.mark.parametrize("path", [LIKE_PATH, UNLIKE_PATH, REPLY_PATH])
    def test_anonymous_redirects_to_login(self, anonymous, monkeypatch, path):
        monkeypatch.setattr(
            views, "authorize_comment_interaction", _forbidden("authorize")
        )
        monkeypatch.setattr(views, "like_comment", _forbidden("like_comment"))
        monkeypatch.setattr(views, "unlike_comment", _forbidden("unlike_comment"))
        monkeypatch.setattr(views, "add_reply", _forbidden("add_reply"))

        response = create_app().dispatch(
            post_request(path, body=form_body(content="hi"))
        )
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_guard_response_is_returned_unchanged(
        self, anonymous, monkeypatch
    ):
        monkeypatch.setattr(
            views, "authorize_comment_interaction", _forbidden("authorize")
        )
        monkeypatch.setattr(views, "like_comment", _forbidden("like_comment"))
        guard = redirect("/login")
        monkeypatch.setattr(views, "require_login", lambda request: guard)
        assert views.comment_like_submit(post_request(LIKE_PATH)) is guard


class TestAuthorizationDenied:
    """E1–E3: a denied interaction renders a readable page and never writes."""

    @pytest.mark.parametrize(
        "path, body",
        [
            (LIKE_PATH, b""),
            (UNLIKE_PATH, b""),
            (REPLY_PATH, b"content=hi"),
        ],
    )
    def test_denied_renders_readable_error(
        self, logged_in, authorize, like, unlike, reply, path, body
    ):
        authorize.fail_with = DENIED_MESSAGE
        response = create_app().dispatch(post_request(path, body=body))
        assert response.status == 200
        assert DENIED_MESSAGE in response.body
        assert '<a href="/">返回首页</a>' in response.body
        assert like.calls == []
        assert unlike.calls == []
        assert reply.calls == []

    def test_denied_message_is_escaped(self, logged_in, authorize, like):
        authorize.fail_with = "<b>坏</b>"
        response = create_app().dispatch(post_request(LIKE_PATH))
        assert "<b>坏</b>" not in response.body
        assert "&lt;b&gt;坏&lt;/b&gt;" in response.body


class TestReplyRejected:
    """F1–F3: a ReplyError renders a readable page and never writes."""

    def test_reply_error_renders_readable_error(
        self, logged_in, authorize, reply
    ):
        reply.fail_with = REPLY_ERROR_MESSAGE
        response = create_app().dispatch(
            post_request(REPLY_PATH, body=form_body(content="   "))
        )
        assert response.status == 200
        assert REPLY_ERROR_MESSAGE in response.body
        assert '<a href="/">' in response.body
        assert "Location" not in response.headers
        assert reply.writes == []

    def test_reply_error_message_is_escaped(self, logged_in, authorize, reply):
        reply.fail_with = "<b>坏</b>"
        response = create_app().dispatch(
            post_request(REPLY_PATH, body=form_body(content="hi"))
        )
        assert "<b>坏</b>" not in response.body
        assert "&lt;b&gt;坏&lt;/b&gt;" in response.body


class TestRouting:
    """G1–G6: the three routes are mounted and dispatchable on the real app."""

    @pytest.mark.parametrize(
        "pattern",
        [
            "/comments/<id>/like",
            "/comments/<id>/unlike",
            "/comments/<id>/replies",
        ],
    )
    def test_routes_registered_on_create_app(self, pattern):
        routes = {(route.method, route.pattern) for route in create_app().routes}
        assert ("POST", pattern) in routes

    def test_register_mounts_routes_on_bare_app(self):
        app = SocialApp()
        views.register(app)
        patterns = {(route.method, route.pattern) for route in app.routes}
        assert ("POST", "/comments/<id>/like") in patterns
        assert ("POST", "/comments/<id>/unlike") in patterns
        assert ("POST", "/comments/<id>/replies") in patterns

    @pytest.mark.parametrize("path", [LIKE_PATH, UNLIKE_PATH, REPLY_PATH])
    def test_get_is_method_not_allowed(self, path):
        response = create_app().dispatch(Request(method="GET", path=path))
        assert response.status == 405
        assert "POST" in response.headers["Allow"]

    def test_submit_reaches_handler_not_placeholder(
        self, logged_in, authorize, like
    ):
        response = create_app().dispatch(post_request(LIKE_PATH))
        assert response.status != 501
        assert "501" not in response.body


class TestPathParams:
    """H1–H2: the ``<id>`` path segment reaches the service as an int."""

    def test_like_path_id_parsed_as_int(self, logged_in, authorize, like):
        views.comment_like_submit(
            post_request("/comments/42/like", params={"id": "42"})
        )
        assert like.calls == [(ACTOR_ID, 42)]

    def test_reply_path_id_parsed_as_int(self, logged_in, authorize, reply):
        views.comment_reply_submit(
            post_request(
                "/comments/42/replies",
                params={"id": "42"},
                body=form_body(content="hi"),
            )
        )
        assert reply.calls == [(42, ACTOR_ID, "hi")]


class TestRealServicesIntegration:
    """Card §6: the fallback services work end-to-end against a temp DB."""

    def _seed(self, tmp_path, monkeypatch):
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
        cur = db.execute(
            "INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
            (post_id, alice, "parent"),
        )
        comment_id = cur.lastrowid
        token = session.create_session(alice)
        return alice, comment_id, token

    def test_like_persists_with_real_services(self, tmp_path, monkeypatch):
        alice, comment_id, token = self._seed(tmp_path, monkeypatch)
        request = Request(
            method="POST",
            path=f"/comments/{comment_id}/like",
            cookies={session.SESSION_COOKIE: token},
        )
        response = create_app().dispatch(request)

        assert response.status == 303
        assert response.headers["Location"] == "/"
        rows = db.query_all(
            "SELECT user_id FROM comment_likes WHERE comment_id = ?",
            (comment_id,),
        )
        assert [row["user_id"] for row in rows] == [alice]

    def test_reply_persists_with_real_services(self, tmp_path, monkeypatch):
        alice, comment_id, token = self._seed(tmp_path, monkeypatch)
        request = Request(
            method="POST",
            path=f"/comments/{comment_id}/replies",
            body=form_body(content="hi"),
            cookies={session.SESSION_COOKIE: token},
        )
        response = create_app().dispatch(request)

        assert response.status == 303
        assert response.headers["Location"] == "/"
        rows = db.query_all(
            "SELECT author_id, content, parent_id FROM comments"
            " WHERE parent_id = ?",
            (comment_id,),
        )
        assert [(r["author_id"], r["content"]) for r in rows] == [(alice, "hi")]


class TestPublicContract:
    """Card §3.2: the module exposes the documented names and constants."""

    def test_paths_and_callables(self):
        assert views.COMMENT_LIKE_PATH == "/comments/<id>/like"
        assert views.COMMENT_UNLIKE_PATH == "/comments/<id>/unlike"
        assert views.COMMENT_REPLY_PATH == "/comments/<id>/replies"
        assert callable(views.comment_like_submit)
        assert callable(views.comment_unlike_submit)
        assert callable(views.comment_reply_submit)
        assert callable(views.register)
