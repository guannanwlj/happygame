"""FP-005 tests: login & logout (social_app/login.py + auth stand-in).

Scenarios documented in docs/test-cases/fp005-login-logout.md. Each test gets
a fresh temp DB (SOCIAL_DB) with the card §6 seed user alice
(password "alice-pass-123", inserted directly since FP-004 is out of scope).
Session state is observed through the test client's cookie jar plus a dummy
login_required-protected route /whoami.
"""

from urllib.parse import parse_qs, urlparse

import pytest

from social_app import auth, db
from social_app.app import create_app

ALICE_PASSWORD = "alice-pass-123"
UNIFIED_ERROR = "用户名或密码错误"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Minimal shell app (FP-002 stand-in) on a fresh temp database."""
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "social_platform.db"))
    application = create_app()
    application.config["TESTING"] = True

    @application.route("/whoami")
    @auth.login_required
    def whoami():
        return str(auth.current_user_id())

    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def seed_alice(app):
    """Card §6 seed: direct INSERT replaces the FP-004 registration flow."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("alice", auth.hash_password(ALICE_PASSWORD)),
    )
    return cur.lastrowid


def redirect_target(resp):
    """Return (path, query dict) of a redirect Location, absolute or relative."""
    parsed = urlparse(resp.headers["Location"])
    return parsed.path, parse_qs(parsed.query)


def session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def login(client, **overrides):
    form = {"username": "alice", "password": ALICE_PASSWORD}
    form.update(overrides)
    return client.post("/login", data=form)


class TestLoginPageRendering:
    """A1/A2: GET /login shows the form and carries `next` through."""

    def test_get_login_renders_form(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "登录" in body
        assert 'name="username"' in body
        assert 'name="password"' in body
        assert 'action="/login"' in body
        assert UNIFIED_ERROR not in body  # no error on first render

    def test_get_login_preserves_next_in_hidden_field(self, client):
        body = client.get("/login", query_string={"next": "/posts"}).get_data(as_text=True)
        assert 'name="next"' in body
        assert "/posts" in body


class TestSuccessfulLogin:
    """Acceptance 1: correct credentials establish the session."""

    def test_correct_credentials_redirect_and_create_session(self, client, seed_alice):
        resp = login(client)
        assert resp.status_code == 302
        path, _ = redirect_target(resp)
        assert path == "/"
        assert session_user_id(client) == seed_alice

    def test_logged_in_user_passes_protected_route(self, client, seed_alice):
        login(client)
        resp = client.get("/whoami")
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == str(seed_alice)

    def test_login_with_safe_next_redirects_there(self, client):
        resp = login(client, next="/posts")
        assert resp.status_code == 302
        path, _ = redirect_target(resp)
        assert path == "/posts"

    def test_failure_then_success_on_same_client(self, client, seed_alice):
        resp = login(client, password="wrong")
        assert UNIFIED_ERROR in resp.get_data(as_text=True)
        assert session_user_id(client) is None

        resp = login(client)
        assert resp.status_code == 302
        assert session_user_id(client) == seed_alice


class TestFailedLogin:
    """Acceptance 2: wrong credentials → unified error, no session."""

    def assert_unified_failure(self, client, resp):
        assert resp.status_code == 200
        assert UNIFIED_ERROR in resp.get_data(as_text=True)
        assert session_user_id(client) is None
        guard = client.get("/whoami")
        assert guard.status_code == 302
        path, query = redirect_target(guard)
        assert path == "/login"
        assert query.get("next") == ["/whoami"]

    def test_unknown_username(self, client):
        self.assert_unified_failure(client, login(client, username="nobody"))

    def test_wrong_password(self, client):
        self.assert_unified_failure(client, login(client, password="not-the-password"))

    def test_empty_username(self, client):
        self.assert_unified_failure(client, login(client, username=""))

    def test_missing_password_field(self, client):
        resp = client.post("/login", data={"username": "alice"})
        self.assert_unified_failure(client, resp)

    def test_username_case_mismatch(self, client):
        self.assert_unified_failure(client, login(client, username="Alice"))

    def test_malformed_stored_hash_fails_closed(self, client):
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("bob", "not-a-valid-hash"),
        )
        self.assert_unified_failure(client, login(client, username="bob", password="whatever"))


class TestLogout:
    """Acceptance 3: logout destroys the session."""

    def test_logout_clears_session_and_redirects_to_login(self, client, seed_alice):
        login(client)
        resp = client.post("/logout")
        assert resp.status_code == 302
        path, _ = redirect_target(resp)
        assert path == "/login"
        assert session_user_id(client) is None

        guard = client.get("/whoami")  # must re-login
        assert guard.status_code == 302
        path, query = redirect_target(guard)
        assert path == "/login"
        assert query.get("next") == ["/whoami"]

    def test_logout_without_session_is_safe(self, client):
        resp = client.post("/logout")
        assert resp.status_code == 302
        path, _ = redirect_target(resp)
        assert path == "/login"
        assert session_user_id(client) is None


class TestNextParamSafety:
    """D: open-redirect hardening on the post-login redirect."""

    def test_absolute_url_next_rejected(self, client):
        resp = login(client, next="http://evil.com")
        assert redirect_target(resp)[0] == "/"

    def test_protocol_relative_next_rejected(self, client):
        resp = login(client, next="//evil.com")
        assert redirect_target(resp)[0] == "/"

    def test_relative_path_without_slash_rejected(self, client):
        resp = login(client, next="friends")
        assert redirect_target(resp)[0] == "/"

    def test_empty_next_falls_back_to_index(self, client):
        resp = login(client, next="")
        assert redirect_target(resp)[0] == "/"


class TestAuthStandIn:
    """E: FP-003 contract slice (inline PBKDF2) behaves per card §3.2."""

    def test_hash_verify_roundtrip(self):
        stored = auth.hash_password("s3cret")
        assert auth.verify_password("s3cret", stored) is True

    def test_wrong_password_rejected(self):
        stored = auth.hash_password("s3cret")
        assert auth.verify_password("s3cret ", stored) is False

    def test_random_salt_per_hash(self):
        assert auth.hash_password("s3cret") != auth.hash_password("s3cret")

    @pytest.mark.parametrize(
        "stored",
        [
            "",
            "garbage",
            "pbkdf2_sha256",
            "pbkdf2_sha256$abc$xy$z",  # non-numeric iterations
            "pbkdf2_md5$60000$abcd$ef01",  # unknown algorithm tag
            "pbkdf2_sha256$60000$!!notb64$$",  # invalid base64
            "pbkdf2_sha256$-1$YWJj$ZGVm",  # non-positive iteration count
        ],
    )
    def test_malformed_stored_hash_returns_false(self, stored):
        assert auth.verify_password("s3cret", stored) is False

    def test_session_helpers_lifecycle(self, app):
        with app.test_request_context():
            assert auth.current_user_id() is None
            auth.login_user(42)
            assert auth.current_user_id() == 42
            auth.logout_user()
            assert auth.current_user_id() is None
