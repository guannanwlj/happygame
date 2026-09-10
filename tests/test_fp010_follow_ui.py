"""FP-010 tests: follow operation UI (social_app.views_follow).

Scenarios documented in docs/test-cases/fp010-follow-ui.md. Requests are
dispatched through a real `create_app()` while the dependencies are isolated
per card §6: FP-011's `social_app.follow_service.follow` is monkeypatched and
FP-003's login guard (`require_login` / `current_user_id`) is stubbed in the
`views_follow` namespace.
"""

from urllib.parse import urlencode

import pytest

from social_app import follow_service
from social_app import views_follow
from social_app.app import Request, Response, SocialApp, create_app, redirect
from social_app.follow_service import FollowError

ACTOR_ID = 42
FOLLOW_PATH = "/follow"


def form_body(**fields) -> bytes:
    return urlencode(fields).encode("utf-8")


def post_follow(body: bytes) -> Response:
    request = Request(method="POST", path=FOLLOW_PATH, body=body)
    return create_app().dispatch(request)


@pytest.fixture
def logged_in(monkeypatch):
    """Simulate an authenticated request (card §6 FP-003 stand-in)."""
    monkeypatch.setattr(views_follow, "require_login", lambda request: None)
    monkeypatch.setattr(views_follow, "current_user_id", lambda request: ACTOR_ID)
    return ACTOR_ID


@pytest.fixture
def anonymous(monkeypatch):
    """Simulate an anonymous request: the guard returns the login redirect."""
    monkeypatch.setattr(
        views_follow, "require_login", lambda request: redirect("/login")
    )
    monkeypatch.setattr(views_follow, "current_user_id", lambda request: None)


@pytest.fixture
def follow_calls(monkeypatch):
    """Patch FP-011's follow() to record calls and succeed."""
    calls: list[tuple[int | None, str]] = []

    def fake_follow(actor_id, target_username):
        calls.append((actor_id, target_username))
        return None

    monkeypatch.setattr(follow_service, "follow", fake_follow)
    return calls


def patch_follow_error(monkeypatch, message: str) -> None:
    def boom(actor_id, target_username):
        raise FollowError(message)

    monkeypatch.setattr(follow_service, "follow", boom)


class TestSuccessFeedback:
    """A1–A3: a valid logged-in follow renders the success page."""

    def test_success_page(self, logged_in, follow_calls):
        response = post_follow(form_body(target_username="bob"))
        assert response.status == 200
        assert "关注成功" in response.body
        assert '<a href="/">' in response.body

    def test_service_called_with_actor_and_target(self, logged_in, follow_calls):
        post_follow(form_body(target_username="bob"))
        assert follow_calls == [(ACTOR_ID, "bob")]

    def test_repeat_follow_is_still_success(self, logged_in, follow_calls):
        post_follow(form_body(target_username="bob"))
        response = post_follow(form_body(target_username="bob"))
        assert response.status == 200
        assert "关注成功" in response.body
        assert "用户不存在" not in response.body


class TestAnonymousRequest:
    """B1–B2: the login guard short-circuits before any follow attempt."""

    def test_redirects_to_login(self, anonymous):
        response = post_follow(form_body(target_username="bob"))
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_never_calls_follow(self, anonymous, monkeypatch):
        def boom(actor_id, target_username):
            raise AssertionError("follow() must not run when not logged in")

        monkeypatch.setattr(follow_service, "follow", boom)
        post_follow(form_body(target_username="bob"))


class TestRuleViolationFeedback:
    """C1–C3: FollowError reasons are rendered as a 200 feedback page."""

    @pytest.mark.parametrize("reason", ["用户不存在", "不能关注自己", "未登录"])
    def test_error_reason_shown(self, logged_in, monkeypatch, reason):
        patch_follow_error(monkeypatch, reason)
        response = post_follow(form_body(target_username="whoever"))
        assert response.status == 200
        assert reason in response.body
        assert '<a href="/">' in response.body


class TestInputHandling:
    """D1–D4: form parsing and the exact target passed to the service."""

    def test_reads_target_from_body(self, logged_in, follow_calls):
        post_follow(form_body(target_username="bob"))
        assert follow_calls == [(ACTOR_ID, "bob")]

    def test_missing_field_is_blank(self, logged_in, follow_calls):
        post_follow(form_body(other="x"))
        assert follow_calls == [(ACTOR_ID, "")]

    def test_blank_field_is_blank(self, logged_in, follow_calls):
        post_follow(b"target_username=")
        assert follow_calls == [(ACTOR_ID, "")]

    def test_extra_fields_are_ignored(self, logged_in, follow_calls):
        post_follow(form_body(target_username="bob", extra="junk"))
        assert follow_calls == [(ACTOR_ID, "bob")]


class TestHtmlEscaping:
    """E1–E3: user-controlled text is escaped in the rendered page."""

    def test_success_escapes_target(self, logged_in, follow_calls):
        payload = "<script>alert(1)</script>"
        response = post_follow(form_body(target_username=payload))
        assert payload not in response.body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.body

    def test_error_escapes_reason(self, logged_in, monkeypatch):
        patch_follow_error(monkeypatch, "<b>坏</b>")
        response = post_follow(form_body(target_username="bob"))
        assert "<b>坏</b>" not in response.body
        assert "&lt;b&gt;坏&lt;/b&gt;" in response.body

    @pytest.mark.parametrize(
        ("payload", "escaped"),
        [("a&b", "a&amp;b"), ("o'brien", "o&#x27;brien")],
    )
    def test_special_characters_escaped(
        self, logged_in, follow_calls, payload, escaped
    ):
        response = post_follow(form_body(target_username=payload))
        assert payload not in response.body
        assert escaped in response.body


class TestRouteMounting:
    """F1–F4: POST /follow is mounted over the FP-010 501 placeholder."""

    def test_create_app_registers_follow_route(self):
        routes = {(route.method, route.pattern) for route in create_app().routes}
        assert ("POST", FOLLOW_PATH) in routes

    def test_placeholder_is_replaced(self, logged_in, follow_calls):
        response = post_follow(form_body(target_username="bob"))
        assert response.status != 501
        assert "501" not in response.body

    def test_register_mounts_handler_on_bare_app(self):
        app = SocialApp()
        views_follow.register(app)
        assert ("POST", FOLLOW_PATH) in {
            (route.method, route.pattern) for route in app.routes
        }

    def test_get_follow_is_method_not_allowed(self, logged_in):
        request = Request(method="GET", path=FOLLOW_PATH)
        response = create_app().dispatch(request)
        assert response.status == 405
        assert "POST" in response.headers["Allow"]
