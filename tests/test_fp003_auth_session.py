"""FP-003 tests: authentication & session management.

Scenarios documented in docs/test-cases/fp003-auth-session.md. DB-backed tests
use a fresh temporary file via SOCIAL_DB (FP-001 pattern); session-helper unit
tests run on plain dicts; HTTP mock-isolation tests monkeypatch the domain
functions imported into social_app.routes so endpoints are verified without
touching the database.
"""

import re

import pytest
from werkzeug.security import generate_password_hash

from social_app import app as app_module
from social_app import auth, db, routes
from social_app.app import create_app
from social_app.routes import login_required

TEST_PASSWORD = "password123"


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so tests never touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    yield str(path)


@pytest.fixture(autouse=True)
def initialized_db(temp_db_path):
    """Start every test from an initialized schema."""
    db.init_db()
    return temp_db_path


@pytest.fixture(scope="module")
def pw_hash():
    """One real password hash reused for cheap user creation."""
    return generate_password_hash(TEST_PASSWORD)


@pytest.fixture()
def client():
    """Flask test client against a TESTING app on the temp DB."""
    app = create_app({"TESTING": True})
    return app.test_client()


def make_user(username: str = "alice", password_hash: str = "h1") -> int:
    """Insert a user row directly, bypassing the register flow."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    return cur.lastrowid


def register_via(client, username="alice", password=TEST_PASSWORD):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login_via(client, username="alice", password=TEST_PASSWORD):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


class TestPasswordHashing:
    """A: hashing primitives."""

    def test_hash_and_verify_roundtrip(self):
        h = auth.hash_password(TEST_PASSWORD)
        assert isinstance(h, str) and h
        assert h != TEST_PASSWORD
        assert auth.verify_password(h, TEST_PASSWORD)

    def test_verify_wrong_password_returns_false(self):
        h = auth.hash_password(TEST_PASSWORD)
        assert auth.verify_password(h, "wrong-password") is False

    def test_same_password_hashes_differ(self):
        h1 = auth.hash_password(TEST_PASSWORD)
        h2 = auth.hash_password(TEST_PASSWORD)
        assert h1 != h2
        assert auth.verify_password(h1, TEST_PASSWORD)
        assert auth.verify_password(h2, TEST_PASSWORD)

    def test_hash_format_and_no_plaintext(self):
        h = auth.hash_password(TEST_PASSWORD)
        assert re.match(r"^[a-z0-9]+:", h)
        assert TEST_PASSWORD not in h


class TestValidation:
    """B: input validation rules."""

    def test_valid_usernames(self):
        assert auth.validate_username("alice") is None
        assert auth.validate_username("ali") is None
        assert auth.validate_username("alice_01") is None
        assert auth.validate_username("a" * 32) is None

    def test_invalid_usernames(self):
        for bad in ("", "a", "ab", "a" * 33, "has space", "no-dash",
                    "ünïcode", 42, None):
            with pytest.raises(auth.ValidationError):
                auth.validate_username(bad)

    def test_password_boundaries(self):
        assert auth.validate_password("a" * 8) is None
        assert auth.validate_password("a" * 128) is None
        for bad in ("a" * 7, "a" * 129, "", 42, None):
            with pytest.raises(auth.ValidationError):
                auth.validate_password(bad)


class TestRegisterUser:
    """C: domain registration against a real DB."""

    def test_register_creates_hashed_user_row(self):
        row = auth.register_user("alice", TEST_PASSWORD)
        assert row["username"] == "alice"
        assert row["id"] and row["created_at"]
        stored = db.query_one("SELECT * FROM users WHERE id = ?", (row["id"],))
        assert stored["password_hash"] != TEST_PASSWORD
        assert auth.verify_password(stored["password_hash"], TEST_PASSWORD)

    def test_duplicate_username_rejected(self):
        auth.register_user("alice", TEST_PASSWORD)
        with pytest.raises(auth.UsernameTakenError):
            auth.register_user("alice", "other-pass-123")
        assert len(db.query_all("SELECT * FROM users")) == 1

    def test_usernames_case_sensitive(self):
        auth.register_user("alice", TEST_PASSWORD)
        row = auth.register_user("Alice", TEST_PASSWORD)
        assert row["username"] == "Alice"

    def test_invalid_input_inserts_nothing(self):
        with pytest.raises(auth.ValidationError):
            auth.register_user("ab", TEST_PASSWORD)
        with pytest.raises(auth.ValidationError):
            auth.register_user("alice", "short")
        assert db.query_one("SELECT * FROM users") is None


class TestAuthenticate:
    """D: credential checking against a real DB."""

    def test_correct_credentials_return_user(self):
        uid = make_user("alice", generate_password_hash(TEST_PASSWORD))
        row = auth.authenticate("alice", TEST_PASSWORD)
        assert row["id"] == uid
        assert row["username"] == "alice"

    def test_wrong_password_raises(self):
        make_user("alice", generate_password_hash(TEST_PASSWORD))
        with pytest.raises(auth.InvalidCredentialsError):
            auth.authenticate("alice", "wrong-password")

    def test_unknown_username_raises_same_error(self):
        make_user("alice", generate_password_hash(TEST_PASSWORD))
        with pytest.raises(auth.InvalidCredentialsError):
            auth.authenticate("nobody", TEST_PASSWORD)

    def test_empty_inputs_raise_invalid_credentials(self):
        make_user("alice", generate_password_hash(TEST_PASSWORD))
        with pytest.raises(auth.InvalidCredentialsError):
            auth.authenticate("", TEST_PASSWORD)
        with pytest.raises(auth.InvalidCredentialsError):
            auth.authenticate("alice", "")


class TestSessionHelpers:
    """E: session helpers on plain dict mocks (no Flask context)."""

    def test_login_session_sets_user_id(self):
        sess = {}
        auth.login_session(sess, 7)
        assert sess["user_id"] == 7

    def test_login_session_clears_stale_keys(self):
        sess = {"cart": [1, 2], "user_id": 99}
        auth.login_session(sess, 7)
        assert sess == {"user_id": 7}

    def test_relogin_replaces_identity(self):
        sess = {}
        auth.login_session(sess, 1)
        auth.login_session(sess, 2)
        assert auth.session_user_id(sess) == 2

    def test_logout_session_clears_and_is_idempotent(self):
        sess = {"user_id": 5, "cart": 1}
        auth.logout_session(sess)
        assert sess == {}
        auth.logout_session(sess)
        assert sess == {}

    def test_session_user_id_anonymous(self):
        assert auth.session_user_id({}) is None

    def test_current_user_variants(self, pw_hash):
        uid = make_user("alice", pw_hash)
        sess = {}
        assert auth.current_user(sess) is None

        auth.login_session(sess, uid)
        assert auth.current_user(sess)["id"] == uid

        db.execute("DELETE FROM users WHERE id = ?", (uid,))
        assert auth.current_user(sess) is None


class TestRegisterEndpoint:
    """F: POST /auth/register via the test client."""

    def test_register_success(self, client):
        r = register_via(client)
        assert r.status_code == 201
        body = r.get_json()
        assert set(body) == {"id", "username"}
        assert body["username"] == "alice"
        stored = db.query_one("SELECT * FROM users WHERE id = ?", (body["id"],))
        assert stored is not None
        assert auth.verify_password(stored["password_hash"], TEST_PASSWORD)

    def test_register_duplicate_conflict(self, client):
        assert register_via(client).status_code == 201
        r = register_via(client)
        assert r.status_code == 409
        assert r.is_json and "error" in r.get_json()

    def test_register_invalid_username(self, client):
        r = register_via(client, username="has space")
        assert r.status_code == 400
        assert r.get_json()["error"]

    def test_register_short_password(self, client):
        r = register_via(client, password="short")
        assert r.status_code == 400
        assert r.get_json()["error"]

    @pytest.mark.parametrize(
        "payload", [{}, {"username": "alice"}, {"password": "x" * 12}]
    )
    def test_register_missing_field(self, client, payload):
        r = client.post("/auth/register", json=payload)
        assert r.status_code == 400

    def test_register_non_json_content_type(self, client):
        r = client.post(
            "/auth/register", data="username=alice", content_type="text/plain"
        )
        assert r.status_code == 415
        assert r.is_json

    def test_register_malformed_json(self, client):
        r = client.post(
            "/auth/register", data="{broken", content_type="application/json"
        )
        assert r.status_code == 400
        assert r.is_json

    def test_responses_never_leak_password_material(self, client):
        register_via(client)
        r = client.get("/auth/me")
        body = r.get_json()
        assert "password" not in body and "password_hash" not in body
        r2 = login_via(client, password="definitely-wrong")
        assert "password" not in r2.get_json()


class TestLoginLogoutMe:
    """G: login / logout / me round trips."""

    def test_login_success_sets_cookie(self, client, pw_hash):
        uid = make_user("alice", pw_hash)
        r = login_via(client)
        assert r.status_code == 200
        assert r.get_json() == {"id": uid, "username": "alice"}
        assert "Set-Cookie" in r.headers

    def test_me_after_login(self, client, pw_hash):
        uid = make_user("alice", pw_hash)
        login_via(client)
        r = client.get("/auth/me")
        assert r.status_code == 200
        assert r.get_json() == {"id": uid, "username": "alice"}

    def test_login_wrong_password(self, client, pw_hash):
        make_user("alice", pw_hash)
        r = login_via(client, password="wrong-password")
        assert r.status_code == 401
        assert r.is_json and "error" in r.get_json()

    def test_login_unknown_user_matches_wrong_password_shape(self, client, pw_hash):
        make_user("alice", pw_hash)
        unknown = login_via(client, username="nobody")
        wrong = login_via(client, password="wrong-password")
        assert unknown.status_code == wrong.status_code == 401
        assert set(unknown.get_json()) == set(wrong.get_json()) == {"error"}

    def test_me_anonymous(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401
        assert r.get_json()["error"]

    def test_logout_clears_session(self, client, pw_hash):
        make_user("alice", pw_hash)
        login_via(client)
        r = client.post("/auth/logout")
        assert r.status_code == 200
        assert r.get_json() == {"ok": True}
        assert client.get("/auth/me").status_code == 401

    def test_logout_anonymous_is_idempotent(self, client):
        r = client.post("/auth/logout")
        assert r.status_code == 200

    def test_relogin_as_other_user(self, client, pw_hash):
        make_user("alice", pw_hash)
        b = make_user("bob", pw_hash)
        login_via(client, "alice")
        login_via(client, "bob")
        r = client.get("/auth/me")
        assert r.get_json() == {"id": b, "username": "bob"}

    def test_register_then_login_roundtrip(self, client):
        reg = register_via(client)
        login = login_via(client)
        assert (reg.status_code, login.status_code) == (201, 200)
        assert reg.get_json()["id"] == login.get_json()["id"]
        assert len(db.query_all("SELECT * FROM users")) == 1


class TestLoginRequired:
    """H: decorator behavior on a protected demo route."""

    @staticmethod
    def protected_client():
        app = create_app({"TESTING": True})

        @app.route("/protected")
        @login_required
        def protected(user_id):
            return {"user_id": user_id}

        return app.test_client()

    def test_anonymous_gets_401_json(self):
        r = self.protected_client().get("/protected")
        assert r.status_code == 401
        assert r.get_json() == {"error": "authentication required"}

    def test_authenticated_handler_receives_user_id(self, pw_hash):
        uid = make_user("alice", pw_hash)
        c = self.protected_client()
        login_via(c)
        r = c.get("/protected")
        assert r.status_code == 200
        assert r.get_json() == {"user_id": uid}


class TestAppFactory:
    """I: embedded FP-002 contract (create_app)."""

    def test_auth_routes_registered(self):
        app = create_app({"TESTING": True})
        rules = {r.rule for r in app.url_map.iter_rules()}
        assert {"/auth/register", "/auth/login", "/auth/logout", "/auth/me"} <= rules

    def test_config_overrides_applied(self):
        app = create_app({"SECRET_KEY": "custom-key", "TESTING": True})
        assert app.secret_key == "custom-key"
        assert app.testing is True

    def test_secret_key_from_env(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_APP_SECRET_KEY", "from-env")
        assert create_app().secret_key == "from-env"

    def test_secret_key_dev_fallback(self, monkeypatch):
        monkeypatch.delenv("SOCIAL_APP_SECRET_KEY", raising=False)
        app = create_app()
        assert app.secret_key == app_module.DEV_SECRET_KEY
        assert app.secret_key

    def test_http_errors_are_json(self):
        c = create_app({"TESTING": True}).test_client()
        r404 = c.get("/nope")
        assert r404.status_code == 404 and r404.is_json
        assert "error" in r404.get_json()
        r405 = c.put("/auth/me")
        assert r405.status_code == 405 and r405.is_json

    def test_factory_initializes_schema(self, tmp_path, monkeypatch):
        other = tmp_path / "factory-only.db"
        monkeypatch.setenv(db.DB_PATH_ENV, str(other))
        create_app()
        assert db.query_one(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ) is not None


class TestRouteMockIsolation:
    """M: endpoints map domain outcomes to HTTP without any DB access."""

    def test_register_delegates_to_domain(self, monkeypatch):
        calls = []

        def fake_register(username, password):
            calls.append((username, password))
            return {"id": 42, "username": username, "created_at": "now"}

        monkeypatch.setattr(routes, "register_user", fake_register)
        client = create_app({"TESTING": True}).test_client()
        r = client.post(
            "/auth/register", json={"username": "ghost", "password": "whatever-12"}
        )
        assert r.status_code == 201
        assert r.get_json() == {"id": 42, "username": "ghost"}
        assert calls == [("ghost", "whatever-12")]

    def test_username_taken_maps_to_409(self, monkeypatch):
        def boom(username, password):
            raise auth.UsernameTakenError("username already taken")

        monkeypatch.setattr(routes, "register_user", boom)
        client = create_app({"TESTING": True}).test_client()
        r = client.post(
            "/auth/register", json={"username": "x", "password": "whatever-12"}
        )
        assert r.status_code == 409
        assert "error" in r.get_json()

    def test_validation_error_maps_to_400(self, monkeypatch):
        def boom(username, password):
            raise auth.ValidationError("bad username")

        monkeypatch.setattr(routes, "register_user", boom)
        client = create_app({"TESTING": True}).test_client()
        r = client.post(
            "/auth/register", json={"username": "x", "password": "whatever-12"}
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "bad username"

    def test_invalid_credentials_maps_to_401(self, monkeypatch):
        def boom(username, password):
            raise auth.InvalidCredentialsError("invalid username or password")

        monkeypatch.setattr(routes, "authenticate", boom)
        client = create_app({"TESTING": True}).test_client()
        r = client.post(
            "/auth/login", json={"username": "x", "password": "whatever-12"}
        )
        assert r.status_code == 401
        assert "error" in r.get_json()
