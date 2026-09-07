"""FP-004 tests: user registration (docs/test-cases/fp004-user-registration.md).

Registration page + form flow on blueprint ``social_app/register.bp``. Uses
the real FP-001 ``db`` module against a fresh ``SOCIAL_DB`` temp file, the
self-built FP-003 ``auth`` stand-in for the hash contract, and a test-local
minimal Flask shell instead of FP-002 ``create_app()`` (unmerged dependency,
mock strategy mirrored from the FP-003 card §6).
"""

import os
import re

import pytest
from flask import Flask

from social_app import db, register
from social_app.auth import verify_password

HASH_RE = re.compile(r"^pbkdf2:sha256\$\d+\$[0-9a-f]+\$[0-9a-f]+$")
ALICE = {"username": "alice", "password": "alice-pass-123"}


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file, initialized schema (FP-001)."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    db.init_db()
    return str(path)


@pytest.fixture()
def app():
    """Minimal Flask shell (FP-002 stand-in) mounting the register blueprint.

    ``Flask("social_app")`` resolves the instance root to the ``social_app``
    package, so the Jinja loader finds ``social_app/templates/``.
    """
    shell = Flask("social_app")
    shell.config.update(TESTING=True, SECRET_KEY="fp004-test-secret-key")
    shell.register_blueprint(register.bp)
    return shell


@pytest.fixture()
def client(app):
    return app.test_client()


def user_rows():
    return db.query_all("SELECT * FROM users")


def user_count():
    return len(user_rows())


class TestRegistrationForm:
    """A: GET /register renders an empty form."""

    def test_form_renders(self, client):
        resp = client.get("/register")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")
        assert "用户注册" in resp.get_data(as_text=True)

    def test_form_markup(self, client):
        html = client.get("/register").get_data(as_text=True)
        assert '<form method="post" action="/register">' in html
        assert 'name="username"' in html
        assert 'name="password"' in html
        assert "<button" in html

    def test_fresh_form_has_no_error(self, client):
        html = client.get("/register").get_data(as_text=True)
        assert 'class="error"' not in html

    def test_get_performs_no_writes(self, client):
        client.get("/register")
        assert user_count() == 0


class TestHappyPath:
    """B: valid submissions create a credential row and hand over to login."""

    def test_redirects_to_login(self, client):
        resp = client.post("/register", data=ALICE)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_row_persisted(self, client):
        client.post("/register", data=ALICE)
        rows = user_rows()
        assert len(rows) == 1
        assert rows[0]["username"] == "alice"
        assert rows[0]["created_at"]  # FP-001 default populated

    def test_password_never_stored_plaintext(self, client):
        client.post("/register", data=ALICE)
        stored = user_rows()[0]["password_hash"]
        assert stored != ALICE["password"]
        assert HASH_RE.match(stored)
        assert ALICE["password"] not in tuple(user_rows()[0])

    def test_hash_verifies_via_auth_contract(self, client):
        client.post("/register", data=ALICE)
        stored = user_rows()[0]["password_hash"]
        assert verify_password(ALICE["password"], stored)
        assert not verify_password("wrong-password", stored)

    def test_success_flash_queued(self, client):
        client.post("/register", data=ALICE)
        with client.session_transaction() as sess:
            flashes = dict(sess.get("_flashes", []))
        assert register.SUCCESS_MESSAGE in flashes.values()

    def test_boundary_values_accepted(self, client):
        resp = client.post(
            "/register", data={"username": "a" * 30, "password": "abc123"}
        )
        assert resp.status_code == 302
        assert user_count() == 1

    def test_same_password_different_hashes(self, client):
        client.post("/register", data=ALICE)
        client.post("/register", data={"username": "bob", "password": ALICE["password"]})
        hashes = [row["password_hash"] for row in user_rows()]
        assert len(hashes) == 2 and hashes[0] != hashes[1]

    def test_username_with_digits_underscore(self, client):
        resp = client.post(
            "/register", data={"username": "user_01", "password": "secret9"}
        )
        assert resp.status_code == 302
        assert user_rows()[0]["username"] == "user_01"


class TestDuplicateUsername:
    """C: username uniqueness (D-004 credential identity)."""

    def test_duplicate_rejected(self, client):
        client.post("/register", data=ALICE)
        resp = client.post("/register", data=ALICE)
        assert resp.status_code == 200
        assert register.USERNAME_TAKEN in resp.get_data(as_text=True)
        assert user_count() == 1

    def test_unique_violation_backstop(self, client, monkeypatch):
        """Pre-check bypassed (race): the UNIQUE index still yields a friendly error."""
        client.post("/register", data=ALICE)
        monkeypatch.setattr(register, "username_exists", lambda username: False)
        resp = client.post("/register", data=ALICE)
        assert resp.status_code == 200
        assert register.USERNAME_TAKEN in resp.get_data(as_text=True)
        assert user_count() == 1

    def test_duplicate_page_preserves_username(self, client):
        client.post("/register", data=ALICE)
        html = client.post("/register", data=ALICE).get_data(as_text=True)
        assert 'value="alice"' in html


class TestUsernameValidation:
    """D: username rules ([A-Za-z0-9_]{3,30} after strip)."""

    @pytest.mark.parametrize(
        "username",
        ["", "   "],
    )
    def test_missing_or_blank(self, client, username):
        resp = client.post(
            "/register", data={"username": username, "password": "secret9"}
        )
        assert resp.status_code == 200
        assert register.USERNAME_REQUIRED in resp.get_data(as_text=True)
        assert user_count() == 0

    def test_username_field_absent(self, client):
        resp = client.post("/register", data={"password": "secret9"})
        assert resp.status_code == 200
        assert register.USERNAME_REQUIRED in resp.get_data(as_text=True)
        assert user_count() == 0

    @pytest.mark.parametrize(
        "username",
        ["ab", "a" * 31, "bad name", "bad-name", "用户名"],
    )
    def test_invalid_shape(self, client, username):
        resp = client.post(
            "/register", data={"username": username, "password": "secret9"}
        )
        assert resp.status_code == 200
        assert register.USERNAME_INVALID in resp.get_data(as_text=True)
        assert user_count() == 0

    def test_username_checked_before_password(self, client):
        resp = client.post("/register", data={"username": "", "password": ""})
        html = resp.get_data(as_text=True)
        assert register.USERNAME_REQUIRED in html
        assert register.PASSWORD_INVALID not in html


class TestPasswordValidation:
    """E: password rules (verbatim, 6–128 chars)."""

    @pytest.mark.parametrize(
        "password",
        ["", "abc12", "x" * 129],
    )
    def test_invalid_password(self, client, password):
        resp = client.post(
            "/register", data={"username": "alice", "password": password}
        )
        assert resp.status_code == 200
        assert register.PASSWORD_INVALID in resp.get_data(as_text=True)
        assert user_count() == 0

    def test_password_field_absent(self, client):
        resp = client.post("/register", data={"username": "alice"})
        assert resp.status_code == 200
        assert register.PASSWORD_INVALID in resp.get_data(as_text=True)
        assert user_count() == 0

    def test_valid_username_echoed_on_password_error(self, client):
        html = client.post(
            "/register", data={"username": "alice", "password": "abc12"}
        ).get_data(as_text=True)
        assert 'value="alice"' in html


class TestOutputEscaping:
    """F: error page echoes untrusted input safely (Jinja autoescape)."""

    def test_script_username_escaped(self, client):
        html = client.post(
            "/register",
            data={"username": "<script>alert(1)</script>", "password": "secret9"},
        ).get_data(as_text=True)
        assert "&lt;script&gt;" in html
        assert "<script>alert" not in html


class TestMountingAndIsolation:
    """G: blueprint contract + default database untouched."""

    def test_blueprint_contract(self):
        assert register.bp.name == "register"
        shell = Flask("social_app")
        shell.config.update(TESTING=True, SECRET_KEY="fp004-test-secret-key")
        shell.register_blueprint(register.bp)
        assert shell.test_client().get("/register").status_code == 200

    def test_default_db_untouched(self, client):
        client.get("/register")
        client.post("/register", data=ALICE)
        assert not os.path.exists(db.DEFAULT_DB_PATH)
