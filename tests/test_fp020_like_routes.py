"""FP-020 tests: like / unlike HTTP entry points (social_app.views_like).

Scenarios documented in docs/test-cases/fp020-like-routes.md. Requests are
dispatched through a real `create_app()` while the dependencies are isolated
per card §6: FP-017's `like`/`unlike` and FP-019's `authorize_interaction` are
monkeypatched in the `views_like` namespace, and FP-003's login guard
(`require_login` / `current_user_id`) is stubbed.
"""

import pytest

from social_app import views_like
from social_app.app import Request, Response, SocialApp, create_app, redirect
from social_app.interaction_service import InteractionError

ACTOR_ID = 42
POST_ID = "7"
LIKE_PATH = f"/posts/{POST_ID}/like"
UNLIKE_PATH = f"/posts/{POST_ID}/unlike"

DENIED_REASON = "无权互动该帖子"


def post(path: str) -> Response:
    request = Request(method="POST", path=path)
    return create_app().dispatch(request)


@pytest.fixture
def logged_in(monkeypatch):
    """Simulate an authenticated request (card §6 FP-003 stand-in)."""
    monkeypatch.setattr(views_like, "require_login", lambda request: None)
    monkeypatch.setattr(views_like, "current_user_id", lambda request: ACTOR_ID)
    return ACTOR_ID


@pytest.fixture
def anonymous(monkeypatch):
    """Simulate an anonymous request: the guard returns the login redirect."""
    monkeypatch.setattr(
        views_like, "require_login", lambda request: redirect("/login")
    )
    monkeypatch.setattr(views_like, "current_user_id", lambda request: None)


@pytest.fixture
def authorized(monkeypatch):
    """Patch FP-019's guard to allow, recording the arguments it saw."""
    calls: list[tuple[int | None, int]] = []

    def allow(actor_id, post_id):
        calls.append((actor_id, post_id))

    monkeypatch.setattr(views_like, "authorize_interaction", allow)
    return calls


@pytest.fixture
def service_calls(monkeypatch):
    """Patch FP-017's like/unlike to record calls and succeed."""
    calls: dict[str, list[tuple[int, int]]] = {"like": [], "unlike": []}

    def fake_like(actor_id, post_id):
        calls["like"].append((actor_id, post_id))
        return 1

    def fake_unlike(actor_id, post_id):
        calls["unlike"].append((actor_id, post_id))
        return 0

    monkeypatch.setattr(views_like, "like", fake_like)
    monkeypatch.setattr(views_like, "unlike", fake_unlike)
    return calls


def patch_denied(monkeypatch, message: str = DENIED_REASON) -> None:
    def deny(actor_id, post_id):
        raise InteractionError(message)

    monkeypatch.setattr(views_like, "authorize_interaction", deny)


def patch_service_forbidden(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("like/unlike must not run")

    monkeypatch.setattr(views_like, "like", boom)
    monkeypatch.setattr(views_like, "unlike", boom)


def patch_guard_forbidden(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("authorize_interaction must not run")

    monkeypatch.setattr(views_like, "authorize_interaction", boom)


class TestLoggedInLike:
    """Acceptance 1: a logged-in, authorized like redirects home."""

    def test_like_logged_in_redirects_home_and_calls_service(
        self, logged_in, authorized, service_calls
    ):
        response = post(LIKE_PATH)
        assert response.status == 303
        assert response.headers["Location"] == "/"
        assert response.body == ""
        assert service_calls["like"] == [(ACTOR_ID, int(POST_ID))]

    def test_like_does_not_call_unlike(
        self, logged_in, authorized, service_calls
    ):
        post(LIKE_PATH)
        assert service_calls["unlike"] == []

    def test_guard_sees_actor_and_post(
        self, logged_in, authorized, service_calls
    ):
        post(LIKE_PATH)
        assert authorized == [(ACTOR_ID, int(POST_ID))]


class TestLoggedInUnlike:
    """Acceptance 2: a logged-in, authorized unlike redirects home."""

    def test_unlike_logged_in_redirects_home(
        self, logged_in, authorized, service_calls
    ):
        response = post(UNLIKE_PATH)
        assert response.status == 303
        assert response.headers["Location"] == "/"
        assert service_calls["unlike"] == [(ACTOR_ID, int(POST_ID))]

    def test_unlike_does_not_call_like(
        self, logged_in, authorized, service_calls
    ):
        post(UNLIKE_PATH)
        assert service_calls["like"] == []


class TestAnonymousRequest:
    """Acceptance 3: the login guard short-circuits before any write."""

    def test_anonymous_redirects_login_and_no_write(self, anonymous, monkeypatch):
        patch_guard_forbidden(monkeypatch)
        patch_service_forbidden(monkeypatch)

        response = post(LIKE_PATH)
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_anonymous_unlike_redirects_login_and_no_write(
        self, anonymous, monkeypatch
    ):
        patch_guard_forbidden(monkeypatch)
        patch_service_forbidden(monkeypatch)

        response = post(UNLIKE_PATH)
        assert response.status == 303
        assert response.headers["Location"] == "/login"


class TestUnauthorizedRequest:
    """Acceptance 4: a denied interaction renders a readable error page."""

    def test_unauthorized_returns_readable_error_and_no_write(
        self, logged_in, monkeypatch, service_calls
    ):
        patch_denied(monkeypatch)
        response = post(LIKE_PATH)
        assert response.status == 200
        assert DENIED_REASON in response.body
        assert '<a href="/">返回首页</a>' in response.body
        assert service_calls["like"] == []

    def test_error_reason_is_escaped(self, logged_in, monkeypatch):
        patch_denied(monkeypatch, "<b>坏</b>")
        response = post(LIKE_PATH)
        assert "<b>坏</b>" not in response.body
        assert "&lt;b&gt;坏&lt;/b&gt;" in response.body

    def test_unlike_denied_renders_readable_error_and_no_write(
        self, logged_in, monkeypatch, service_calls
    ):
        patch_denied(monkeypatch)
        response = post(UNLIKE_PATH)
        assert response.status == 200
        assert DENIED_REASON in response.body
        assert service_calls["unlike"] == []


class TestRouteMounting:
    """Card §3.2/§4: routes are mounted and the id flows to the service."""

    def test_routes_mounted_in_create_app(self):
        routes = {(route.method, route.pattern) for route in create_app().routes}
        assert ("POST", "/posts/<id>/like") in routes
        assert ("POST", "/posts/<id>/unlike") in routes

    def test_register_mounts_routes_on_bare_app(self):
        app = SocialApp()
        views_like.register(app)
        patterns = {(route.method, route.pattern) for route in app.routes}
        assert ("POST", "/posts/<id>/like") in patterns
        assert ("POST", "/posts/<id>/unlike") in patterns

    @pytest.mark.parametrize("path", [LIKE_PATH, UNLIKE_PATH])
    def test_get_is_method_not_allowed(self, path):
        response = create_app().dispatch(Request(method="GET", path=path))
        assert response.status == 405
        assert "POST" in response.headers["Allow"]

    def test_path_id_reaches_service(
        self, logged_in, authorized, service_calls
    ):
        post("/posts/123/like")
        assert service_calls["like"] == [(ACTOR_ID, 123)]

    def test_public_contract_is_callable(self):
        assert callable(views_like.like_submit)
        assert callable(views_like.unlike_submit)
        assert callable(views_like.register)
