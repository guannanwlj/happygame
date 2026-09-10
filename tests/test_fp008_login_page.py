"""FP-008 tests: login page and logout (social_app.views_login).

Scenarios documented in docs/test-cases/fp008-login-page.md. Requests go
through the real FP-001 ``create_app()`` registry via ``dispatch``;
FP-009 auth and FP-003 session invalidation are monkeypatched on the
``social_app.views_login`` module (card §6 mock strategy).
"""

import pytest

from social_app import views_login
from social_app.app import Request, SocialApp, create_app
from social_app.session import clear_cookie_header, cookie_header


def request(method="GET", path="/login", body=b"", cookies=None):
    """Card §6 request stand-in with the real FP-001 Request dataclass."""
    return Request(
        method=method, path=path, body=body, cookies=cookies or {}
    )


def dispatch(app, method="GET", path="/login", body=b"", cookies=None):
    return app.dispatch(request(method, path, body, cookies))


def mock_login(monkeypatch, result, calls=None):
    """Patch the FP-009 seam; optionally record (username, password) calls."""

    def fake_login(username, password):
        if calls is not None:
            calls.append((username, password))
        return result

    monkeypatch.setattr(views_login, "login", fake_login)


@pytest.fixture()
def app():
    return create_app()


class TestAcceptance:
    """A1–A4: the card §7 acceptance criteria."""

    def test_get_login_renders_form(self, app):
        response = dispatch(app)
        assert response.status == 200
        assert response.content_type.startswith("text/html")
        assert 'name="username"' in response.body
        assert 'name="password"' in response.body

    def test_login_success_redirects_with_session_cookie(self, app, monkeypatch):
        mock_login(monkeypatch, "tok-1")
        response = dispatch(
            app,
            method="POST",
            body=b"username=alice&password=secret1",
        )
        assert response.status == 303
        assert response.headers["Location"] == "/"
        assert response.headers["Set-Cookie"] == cookie_header("tok-1")

    def test_login_failure_renders_error_without_redirect(self, app, monkeypatch):
        mock_login(monkeypatch, None)
        response = dispatch(
            app,
            method="POST",
            body=b"username=alice&password=wrong",
        )
        assert response.status == 200
        assert "认证失败" in response.body
        assert "Location" not in response.headers

    def test_logout_destroys_session_and_clears_cookie(self, app, monkeypatch):
        destroyed = []
        monkeypatch.setattr(views_login, "destroy_session", destroyed.append)
        response = dispatch(
            app, method="POST", path="/logout", cookies={"session": "tok-1"}
        )
        assert destroyed == ["tok-1"]
        assert response.status == 303
        assert response.headers["Location"] == "/login"
        assert response.headers["Set-Cookie"] == clear_cookie_header()


class TestLoginPage:
    """B1–B4: form rendering and the logout entry."""

    def test_page_has_login_title(self, app):
        response = dispatch(app)
        assert "<title>登录</title>" in response.body

    def test_form_posts_to_login(self, app):
        body = dispatch(app).body
        assert 'action="/login"' in body
        assert 'method="post"' in body

    def test_page_exposes_logout_entry(self, app):
        body = dispatch(app).body
        assert 'action="/logout"' in body

    def test_get_login_is_not_the_501_placeholder(self, app):
        response = dispatch(app)
        assert response.status == 200
        assert "501" not in response.body


class TestLoginSubmit:
    """C1–C5: parsing, success and failure paths."""

    def test_credentials_are_passed_to_auth(self, app, monkeypatch):
        calls = []
        mock_login(monkeypatch, "tok-1", calls)
        dispatch(
            app,
            method="POST",
            body=b"username=alice&password=secret1",
        )
        assert calls == [("alice", "secret1")]

    def test_success_body_is_not_the_form(self, app, monkeypatch):
        mock_login(monkeypatch, "tok-1")
        response = dispatch(
            app, method="POST", body=b"username=alice&password=secret1"
        )
        assert "认证失败" not in response.body

    def test_empty_body_is_a_failure(self, app, monkeypatch):
        calls = []
        mock_login(monkeypatch, None, calls)
        response = dispatch(app, method="POST", body=b"")
        assert calls == [("", "")]
        assert response.status == 200
        assert "认证失败" in response.body

    def test_failure_escapes_echoed_username(self, app, monkeypatch):
        mock_login(monkeypatch, None)
        response = dispatch(
            app,
            method="POST",
            body=b"username=%3Cscript%3E&password=x",
        )
        assert "&lt;script&gt;" in response.body
        assert "<script>" not in response.body

    def test_failure_keeps_the_username_value(self, app, monkeypatch):
        mock_login(monkeypatch, None)
        response = dispatch(
            app,
            method="POST",
            body=b"username=alice&password=wrong",
        )
        assert 'value="alice"' in response.body


class TestLogout:
    """D1–D4: session invalidation and cookie clearing."""

    def test_redirect_target(self, app, monkeypatch):
        monkeypatch.setattr(views_login, "destroy_session", lambda token: None)
        response = dispatch(
            app, method="POST", path="/logout", cookies={"session": "tok-1"}
        )
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_without_cookie_destroys_none_and_clears(self, app, monkeypatch):
        destroyed = []
        monkeypatch.setattr(views_login, "destroy_session", destroyed.append)
        response = dispatch(app, method="POST", path="/logout")
        assert destroyed == [None]
        assert response.status == 303
        assert response.headers["Set-Cookie"] == clear_cookie_header()

    def test_other_cookies_are_ignored(self, app, monkeypatch):
        destroyed = []
        monkeypatch.setattr(views_login, "destroy_session", destroyed.append)
        dispatch(
            app,
            method="POST",
            path="/logout",
            cookies={"theme": "dark"},
        )
        assert destroyed == [None]

    def test_get_logout_is_not_allowed(self, app):
        response = dispatch(app, method="GET", path="/logout")
        assert response.status == 405
        assert "POST" in response.headers["Allow"]


class TestRouteMounting:
    """E1–E3 / F: register and create_app wiring."""

    def test_register_installs_the_three_routes(self):
        application = SocialApp()
        views_login.register(application)
        routes = {(route.method, route.pattern) for route in application.routes}
        assert routes == {
            ("GET", "/login"),
            ("POST", "/login"),
            ("POST", "/logout"),
        }

    def test_create_app_has_all_login_routes(self, app):
        routes = {(route.method, route.pattern) for route in app.routes}
        assert routes >= {
            ("GET", "/login"),
            ("POST", "/login"),
            ("POST", "/logout"),
        }

    def test_success_cookie_matches_fp003_helper(self, app, monkeypatch):
        mock_login(monkeypatch, "tok-42")
        response = dispatch(
            app, method="POST", body=b"username=a&password=b"
        )
        assert response.headers["Set-Cookie"] == cookie_header("tok-42")
