"""FP-003 tests: session management & protected-page access control (social_app/guard.py).

Scenarios documented in docs/test-cases/fp003-session-guard.md. Per task card
§6 the demo blueprint lives only in this test module: until FP-001's
create_app lands we mount it on a minimal Flask(__name__) app, afterwards on
the real factory. Seed rows go through social_app.db with SOCIAL_DB pointed
at a fresh temp file.
"""

import pytest
from flask import Blueprint, Flask, Response, session

from social_app import db, guard

SECRET = "fp003-test-secret"
PROTECTED_PATH = "/demo-protected"


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so tests never touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    yield str(path)


@pytest.fixture(autouse=True)
def seeded_db(temp_db_path):
    """Card §6 seed: alice (id=1) plus a second user for the overwrite case."""
    db.init_db()
    db.execute(
        "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        (1, "alice", "h"),
    )
    db.execute(
        "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        (2, "bob", "h2"),
    )


def _demo_blueprint():
    """Test-only protected blueprint exercising every guard primitive."""
    bp = Blueprint("demo_guard", __name__)

    @bp.route(PROTECTED_PATH, methods=["GET", "POST"])
    @guard.login_required
    def protected():
        return Response(f"ok:{guard.current_user_id()}", status=200)

    @bp.route("/demo-login/<int:user_id>")
    def demo_login(user_id: int):
        guard.login_user(user_id)
        return Response("logged-in", status=200)

    @bp.route("/demo-logout")
    def demo_logout():
        guard.logout_user()
        return Response("logged-out", status=200)

    @bp.route("/demo-whoami")
    @guard.login_required
    def whoami():
        return Response(str(guard.current_user_id()), status=200)

    return bp


@pytest.fixture()
def app():
    """Demo app: FP-001's create_app when merged, else a minimal Flask app (§6)."""
    try:
        from social_app.app import create_app
    except ImportError:
        application = Flask(__name__)
        application.secret_key = SECRET
    else:
        application = create_app()
        if not application.secret_key:
            application.secret_key = SECRET
    application.register_blueprint(_demo_blueprint())
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def login_session(client, user_id: int) -> None:
    """Simulate an existing login directly in the session cookie."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


class TestUnauthenticatedRedirect:
    """Acceptance 1 (A): unauthenticated access is redirected to /login."""

    def test_get_without_session_redirects_to_login(self, client):
        resp = client.get(PROTECTED_PATH)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/login"

    def test_redirect_uses_literal_path_without_login_endpoint(self, app, client):
        """D4: no /login route or endpoint exists anywhere, redirect still works."""
        assert "login" not in {r.rule for r in app.url_map.iter_rules()}
        resp = client.get(PROTECTED_PATH)
        assert resp.headers["Location"] == "/login"

    def test_post_without_session_also_redirected(self, client):
        resp = client.post(PROTECTED_PATH, data={"text": "hi"})
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/login"

    def test_logged_in_get_passes_through(self, client):
        login_session(client, 1)
        resp = client.get(PROTECTED_PATH)
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == "ok:1"


class TestLogoutDestroysSession:
    """Acceptance 2 (B): logout_user destroys the session, next access blocked."""

    def test_logout_then_access_is_redirected(self, client):
        login_session(client, 1)
        assert client.get(PROTECTED_PATH).status_code == 200

        out = client.get("/demo-logout")
        assert out.status_code == 200

        resp = client.get(PROTECTED_PATH)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/login"
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_logout_clears_entire_session(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["csrf"] = "token"
        client.get("/demo-logout")
        with client.session_transaction() as sess:
            assert "user_id" not in sess
            assert "csrf" not in sess


class TestReloginOverwritesSession:
    """Acceptance 3 (C): login_user overwrites the previous session."""

    def test_login_user_overrides_old_value(self, app):
        with app.test_request_context():
            guard.login_user(1)
            guard.login_user(2)
            assert guard.current_user_id() == 2

    def test_overwrite_visible_to_next_request(self, client):
        login_session(client, 1)
        assert client.get("/demo-whoami").get_data(as_text=True) == "1"

        client.get("/demo-login/2")

        assert client.get("/demo-whoami").get_data(as_text=True) == "2"
        with client.session_transaction() as sess:
            assert sess["user_id"] == 2


class TestCurrentUserIdContract:
    """D1/D2: current_user_id and primitive session-proxy behaviour."""

    def test_current_user_id_none_when_signed_out(self, app):
        with app.test_request_context():
            assert guard.current_user_id() is None

    def test_primitives_bind_to_flask_session_proxy(self, app):
        with app.test_request_context():
            assert guard.current_user_id() is None
            guard.login_user(1)
            assert session["user_id"] == 1
            guard.login_user(2)
            assert session["user_id"] == 2
            guard.logout_user()
            assert session.get("user_id") is None

    def test_login_required_preserves_view_metadata(self):
        @guard.login_required
        def sample_view():
            """docs"""

        assert sample_view.__name__ == "sample_view"
        assert sample_view.__doc__ == "docs"
