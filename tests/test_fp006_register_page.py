"""FP-006 tests: the registration page and submit orchestration.

Scenarios documented in docs/test-cases/fp006-register-page.md. Handlers are
driven directly through ``SocialApp.dispatch(Request(...))`` (card §8), and
FP-007 (``social_app.accounts``) is substituted per card §6 so no database or
real account core is needed.
"""

import sys
import types
from urllib.parse import urlencode

import pytest

from social_app import session
from social_app.app import Request, SocialApp, create_app
from social_app.views_register import register, register_page, register_submit


class RegisterError(Exception):
    """Stand-in for ``social_app.accounts.RegisterError`` when FP-007 is absent."""


@pytest.fixture
def accounts_mod(monkeypatch):
    """Return a substitutable ``social_app.accounts`` module (card §6).

    Uses the real FP-007 module when it is mounted; otherwise installs a
    minimal stub so the lazy import in ``views_register`` resolves.
    """
    module = sys.modules.get("social_app.accounts")
    if module is None:
        module = types.ModuleType("social_app.accounts")
        module.RegisterError = RegisterError
        module.register = lambda username, password: (0, "")
        sys.modules["social_app.accounts"] = module
        import social_app

        social_app.accounts = module
    return module


class FakeRegister:
    """Records calls and returns/raises on demand (card §6 stub)."""

    def __init__(self, module):
        self.module = module
        self.calls = []
        self.result = (1, "tok")
        self.error = None

    def __call__(self, username, password):
        self.calls.append((username, password))
        if self.error is not None:
            raise self.module.RegisterError(self.error)
        return self.result


@pytest.fixture
def fake_register(accounts_mod, monkeypatch):
    """Install and return the FP-007 stub on the accounts module."""
    fake = FakeRegister(accounts_mod)
    monkeypatch.setattr(accounts_mod, "register", fake)
    return fake


def post(body: bytes):
    return Request(method="POST", path="/register", body=body)


class TestAcceptance:
    """A1-A4: card §7 acceptance criteria."""

    def test_get_register_renders_form(self):
        response = register_page(Request(method="GET", path="/register"))
        assert response.status == 200
        assert response.content_type.startswith("text/html")
        assert 'name="username"' in response.body
        assert 'name="password"' in response.body
        assert "<button" in response.body

    def test_valid_submit_redirects_home_with_session_cookie(self, fake_register):
        response = register_submit(
            post(b"username=alice&password=secret1")
        )
        assert response.status == 303
        assert response.headers["Location"] == "/"
        assert response.headers["Set-Cookie"] == "session=tok; HttpOnly; Path=/"
        assert fake_register.calls == [("alice", "secret1")]

    def test_invalid_submit_rerenders_with_reason(self, fake_register):
        fake_register.error = "用户名已被占用"
        response = register_submit(post(b"username=alice&password=secret1"))
        assert response.status == 200
        assert "用户名已被占用" in response.body
        assert "Location" not in response.headers
        assert "Set-Cookie" not in response.headers

    def test_username_is_escaped_on_echo(self, fake_register):
        fake_register.error = "用户名已被占用"
        body = urlencode(
            {"username": "<script>alert(1)</script>", "password": "secret1"}
        ).encode()
        response = register_submit(post(body))
        assert "&lt;script&gt;" in response.body
        assert "<script>" not in response.body


class TestFormDelegation:
    """B1-B4: parse_form → accounts.register delegation."""

    def test_plain_fields_forwarded(self, fake_register):
        register_submit(post(b"username=alice&password=secret1"))
        assert fake_register.calls == [("alice", "secret1")]

    def test_encoded_fields_decoded(self, fake_register):
        body = urlencode({"username": "a b", "password": "p@ss"}).encode()
        assert body == b"username=a+b&password=p%40ss"
        register_submit(post(body))
        assert fake_register.calls == [("a b", "p@ss")]

    def test_empty_body_forwards_blank_fields(self, fake_register):
        register_submit(post(b""))
        assert fake_register.calls == [("", "")]

    def test_extra_fields_ignored(self, fake_register):
        register_submit(post(b"username=alice&password=secret1&admin=1"))
        assert fake_register.calls == [("alice", "secret1")]


class TestCookieContract:
    """C1-C3: the Set-Cookie value comes from FP-003."""

    def test_set_cookie_matches_cookie_header(self, fake_register):
        fake_register.result = (7, "tok-7")
        response = register_submit(post(b"username=alice&password=secret1"))
        assert response.headers["Set-Cookie"] == session.cookie_header("tok-7")

    def test_set_cookie_flags(self, fake_register):
        response = register_submit(post(b"username=alice&password=secret1"))
        cookie = response.headers["Set-Cookie"]
        assert cookie.startswith("session=")
        assert "HttpOnly" in cookie
        assert "Path=/" in cookie

    def test_failure_emits_no_cookie(self, fake_register):
        fake_register.error = "密码至少 6 位"
        response = register_submit(post(b"username=alice&password=123"))
        assert "Set-Cookie" not in response.headers


class TestMounting:
    """D1-D4: register(app) / create_app() wiring."""

    def test_register_mounts_both_handlers(self):
        app = SocialApp()
        register(app)
        routes = {(r.method, r.pattern): r.handler for r in app.routes}
        assert routes[("GET", "/register")] is register_page
        assert routes[("POST", "/register")] is register_submit

    def test_create_app_serves_real_handlers(self, fake_register):
        app = create_app()
        response = app.dispatch(Request(method="GET", path="/register"))
        assert response.status == 200
        assert 'name="username"' in response.body

    def test_create_app_submit_is_mounted(self, fake_register):
        app = create_app()
        response = app.dispatch(post(b"username=alice&password=secret1"))
        assert response.status == 303
        assert response.headers["Location"] == "/"

    def test_register_is_idempotent(self):
        app = SocialApp()
        register(app)
        register(app)
        pairs = [(r.method, r.pattern) for r in app.routes]
        assert pairs.count(("GET", "/register")) == 1
        assert pairs.count(("POST", "/register")) == 1

    def test_create_app_route_table_has_register(self):
        routes = {(r.method, r.pattern) for r in create_app().routes}
        assert {("GET", "/register"), ("POST", "/register")} <= routes


class TestRendering:
    """E1-E4: page structure, escaping and GET purity."""

    def test_form_structure(self):
        response = register_page(Request(method="GET", path="/register"))
        assert response.body.startswith("<!DOCTYPE html>")
        assert 'action="/register"' in response.body
        assert 'method="post"' in response.body
        assert "注册" in response.body

    def test_error_rerender_keeps_username_escaped(self, fake_register):
        fake_register.error = "用户名已被占用"
        body = urlencode({"username": "<b>al</b>", "password": "secret1"}).encode()
        page = register_submit(post(body)).body
        assert "&lt;b&gt;al&lt;/b&gt;" in page
        assert "<b>al</b>" not in page

    def test_error_message_escaped(self, fake_register):
        fake_register.error = "<b>bad</b>"
        page = register_submit(post(b"username=alice&password=secret1")).body
        assert "&lt;b&gt;bad&lt;/b&gt;" in page
        assert "<b>bad</b>" not in page

    def test_get_does_not_call_accounts(self, fake_register):
        register_page(Request(method="GET", path="/register"))
        assert fake_register.calls == []
