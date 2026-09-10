"""FP-003 tests: session / login state (social_app.session).

Scenarios documented in docs/test-cases/fp003-session.md. Per card §6 the
web framework stand-ins are minimal: requests are SimpleNamespace objects
with a `cookies` dict, and `social_app.session.redirect` is monkeypatched /
asserted directly (no FP-001 dependency).
"""

import threading
from types import SimpleNamespace

import pytest

from social_app import session


@pytest.fixture(autouse=True)
def clean_sessions():
    """Isolate every test from the process-wide session store."""
    with session._lock:
        session._sessions.clear()
    yield
    with session._lock:
        session._sessions.clear()


def request_with(cookies):
    """Card §6 minimal request stand-in (only needs `.cookies`)."""
    return SimpleNamespace(cookies=cookies)


def logged_in(token):
    return request_with({session.SESSION_COOKIE: token})


class TestAcceptance:
    """A1–A6: the card §7 acceptance criteria."""

    def test_create_session_then_get_user_id(self):
        token = session.create_session(7)
        assert session.get_user_id(token) == 7

    def test_current_user_id_reads_cookie(self):
        token = session.create_session(7)
        assert session.current_user_id(logged_in(token)) == 7

    def test_require_login_redirects_anonymous(self):
        response = session.require_login(request_with({}))
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_require_login_allows_logged_in(self):
        token = session.create_session(7)
        assert session.require_login(logged_in(token)) is None

    def test_destroy_session_invalidates_and_is_idempotent(self):
        token = session.create_session(7)
        session.destroy_session(token)
        assert session.get_user_id(token) is None
        session.destroy_session(token)
        assert session.get_user_id(token) is None

    def test_cookie_headers(self):
        header = session.cookie_header("abc123")
        assert "session=abc123" in header
        assert "HttpOnly" in header
        assert "Path=/" in header

        cleared = session.clear_cookie_header()
        assert "Max-Age=0" in cleared
        assert cleared.startswith("session=")


class TestEstablishment:
    """B1–B5: token generation and lookup."""

    def test_tokens_are_unique(self):
        tokens = {session.create_session(1) for _ in range(200)}
        assert len(tokens) == 200

    def test_token_is_url_safe_and_long(self):
        token = session.create_session(1)
        assert len(token) >= 32
        for char in token:
            assert char.isalnum() or char in "-_"

    def test_sessions_are_isolated_per_user(self):
        first = session.create_session(1)
        second = session.create_session(2)
        assert session.get_user_id(first) == 1
        assert session.get_user_id(second) == 2

    @pytest.mark.parametrize("token", [None, "", "not-a-real-token"])
    def test_invalid_tokens_return_none(self, token):
        assert session.get_user_id(token) is None

    def test_user_id_zero_is_not_confused_with_missing(self):
        token = session.create_session(0)
        assert session.get_user_id(token) == 0


class TestInvalidation:
    """C1–C4: destroy semantics."""

    def test_destroy_unknown_token_does_not_raise(self):
        session.destroy_session("never-created")

    @pytest.mark.parametrize("token", [None, ""])
    def test_destroy_missing_token_does_not_raise(self, token):
        session.destroy_session(token)

    def test_destroy_one_session_leaves_others(self):
        keep = session.create_session(1)
        drop = session.create_session(2)
        session.destroy_session(drop)
        assert session.get_user_id(keep) == 1
        assert session.get_user_id(drop) is None

    def test_recreate_after_destroy(self):
        old = session.create_session(1)
        session.destroy_session(old)
        new = session.create_session(1)
        assert new != old
        assert session.get_user_id(new) == 1
        assert session.get_user_id(old) is None


class TestCurrentUser:
    """D1–D5: request integration."""

    def test_resolves_from_cookies(self):
        token = session.create_session(7)
        assert session.current_user_id(request_with({"session": token})) == 7

    def test_request_without_cookies_attribute_is_anonymous(self):
        assert session.current_user_id(SimpleNamespace()) is None

    def test_unknown_and_empty_cookies_are_anonymous(self):
        assert session.current_user_id(request_with({})) is None
        assert session.current_user_id(
            request_with({"session": "bogus"})
        ) is None

    def test_other_cookies_are_ignored(self):
        request = request_with({"theme": "dark", "session": ""})
        assert session.current_user_id(request) is None

    def test_session_cookie_name(self):
        assert session.SESSION_COOKIE == "session"


class TestRequireLogin:
    """E1–E5: guard behaviour and redirect delegation."""

    @pytest.mark.parametrize("cookies", [{}, {"session": ""}, {"session": "x"}])
    def test_anonymous_variants_redirect(self, cookies):
        response = session.require_login(request_with(cookies))
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_request_without_cookies_is_redirected(self):
        response = session.require_login(SimpleNamespace())
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_destroyed_session_is_redirected(self):
        token = session.create_session(1)
        session.destroy_session(token)
        response = session.require_login(logged_in(token))
        assert response.status == 303

    def test_redirect_uses_login_path(self, monkeypatch):
        calls = []

        def fake_redirect(location, status=303):
            calls.append((location, status))
            return SimpleNamespace(status=status, headers={"Location": location})

        monkeypatch.setattr(session, "redirect", fake_redirect)
        response = session.require_login(request_with({}))
        assert calls == [("/login", 303)]
        assert response.headers["Location"] == "/login"

    def test_logged_in_does_not_call_redirect(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise AssertionError("redirect must not run for logged-in requests")

        monkeypatch.setattr(session, "redirect", boom)
        token = session.create_session(1)
        assert session.require_login(logged_in(token)) is None


class TestCookieHeaders:
    """F1–F3: exact header literals and no side effects."""

    def test_cookie_header_exact(self):
        assert session.cookie_header("tok") == (
            "session=tok; HttpOnly; Path=/"
        )

    def test_clear_cookie_header_exact(self):
        assert session.clear_cookie_header() == (
            "session=; HttpOnly; Path=/; Max-Age=0"
        )

    def test_header_helpers_do_not_touch_store(self):
        token = session.create_session(1)
        session.cookie_header(token)
        session.clear_cookie_header()
        assert session.get_user_id(token) == 1


class TestThreadSafety:
    """G1–G2: smoke tests for concurrent access."""

    def test_concurrent_create_sessions(self):
        results: dict[int, str] = {}
        lock = threading.Lock()

        def worker(user_id):
            token = session.create_session(user_id)
            with lock:
                results[user_id] = token

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert len(set(results.values())) == 8
        for user_id, token in results.items():
            assert session.get_user_id(token) == user_id

    def test_concurrent_destroy_is_safe(self):
        token = session.create_session(1)
        errors: list[BaseException] = []

        def worker():
            try:
                session.destroy_session(token)
            except BaseException as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert errors == []
        assert session.get_user_id(token) is None
