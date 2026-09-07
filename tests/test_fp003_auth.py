"""FP-003 tests: authentication & session management (task card §7/§8).

Scenarios documented in docs/test-cases/fp003-auth-session.md. The DB-backed
group uses the real FP-001 module against a temp ``SOCIAL_DB``; the HTTP
groups use a test-local minimal Flask shell because FP-002 is not merged
(card §6 mock strategy).
"""

import os
import re

import pytest
from flask import Flask, session

from social_app import auth, db

ALICE_PASSWORD = "alice-pass-123"  # seed credentials, card §6
HASH_RE = re.compile(r"^pbkdf2:sha256\$(\d+)\$([0-9a-f]{32})\$([0-9a-f]{64})$")


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so no test can touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    return str(path)


@pytest.fixture()
def users_db(temp_db_path):
    """Initialized FP-001 schema for DB-backed scenarios."""
    db.init_db()
    return temp_db_path


def seed_user(username: str, password: str) -> int:
    """Insert a seed user with a real hash (card §6); return the new id."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, auth.hash_password(password)),
    )
    return cur.lastrowid


@pytest.fixture()
def shell():
    """Minimal Flask app (FP-002 stand-in, card §6) with driver routes."""
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="fp003-test-secret-key")
    app.config["HITS"] = []

    @app.get("/protected")
    @auth.login_required
    def protected():
        app.config["HITS"].append(auth.current_user_id())
        return {"user_id": auth.current_user_id()}

    @app.get("/posts/<int:post_id>/comments")
    @auth.login_required
    def post_comments(post_id):
        return {"post_id": post_id, "user_id": auth.current_user_id()}

    @app.get("/test-login/<int:user_id>")
    def test_login(user_id):
        auth.login_user(user_id)
        return {"ok": True}

    @app.get("/test-logout")
    def test_logout():
        auth.logout_user()
        return {"ok": True}

    return app


class TestPasswordHashing:
    """A: hashing primitives (card §7 case 1)."""

    def test_hash_format_hides_plaintext(self):
        stored = auth.hash_password(ALICE_PASSWORD)
        assert HASH_RE.fullmatch(stored)
        assert stored != ALICE_PASSWORD
        assert ALICE_PASSWORD not in stored

    def test_roundtrip(self):
        stored = auth.hash_password("s3cret-pass")
        assert auth.verify_password("s3cret-pass", stored) is True

    def test_wrong_password_returns_false(self):
        stored = auth.hash_password("s3cret-pass")
        assert auth.verify_password("wrong-pass", stored) is False

    def test_same_password_yields_different_salts(self):
        h1 = auth.hash_password("dup-pass-123")
        h2 = auth.hash_password("dup-pass-123")
        assert h1 != h2
        assert auth.verify_password("dup-pass-123", h1) is True
        assert auth.verify_password("dup-pass-123", h2) is True


class TestVerifyRobustness:
    """B: malformed / hostile stored hashes must yield False, never raise."""

    def test_empty_and_garbage_stored(self):
        assert auth.verify_password("x", "") is False
        assert auth.verify_password("x", "not-a-hash") is False

    def test_wrong_field_count(self):
        assert auth.verify_password("x", "pbkdf2:sha256$600000$abcd") is False
        assert auth.verify_password(
            "x", "pbkdf2:sha256$600000$abcd$ef$extra"
        ) is False

    def test_unknown_method(self):
        stored = f"scrypt$600000${'ab' * 16}${'cd' * 32}"
        assert auth.verify_password("x", stored) is False

    @pytest.mark.parametrize("iterations", ["0", "-1", "abc", ""])
    def test_bad_iteration_counts(self, iterations):
        stored = f"pbkdf2:sha256${iterations}${'ab' * 16}${'cd' * 32}"
        assert auth.verify_password("x", stored) is False

    def test_absurd_iteration_count_rejected_before_kdf(self):
        stored = f"pbkdf2:sha256$2000000000${'ab' * 16}${'cd' * 32}"
        assert auth.verify_password("x", stored) is False

    def test_non_hex_salt_and_digest(self):
        stored = f"pbkdf2:sha256$600000$zz{'ab' * 15}${'cd' * 32}"
        assert auth.verify_password("x", stored) is False
        stored = f"pbkdf2:sha256$600000${'ab' * 16}$zz{'cd' * 31}"
        assert auth.verify_password("x", stored) is False

    @pytest.mark.parametrize("stored", [42, None, ["pbkdf2"], 3.14, b"bytes"])
    def test_non_string_stored(self, stored):
        assert auth.verify_password("x", stored) is False

    def test_single_flipped_digest_char_fails(self):
        stored = auth.hash_password("flip-pass-123")
        method, iterations, salt, digest = stored.split("$")
        replacement = "0" if digest[-1] != "0" else "1"
        tampered = f"{method}${iterations}${salt}${digest[:-1]}{replacement}"
        assert auth.verify_password("flip-pass-123", tampered) is False


class TestCredentialStorage:
    """C: seed & check credentials against the real FP-001 users table."""

    def test_seed_user_stores_verifiable_hash_not_plaintext(self, users_db):
        uid = seed_user("alice", ALICE_PASSWORD)
        row = db.query_one("SELECT * FROM users WHERE username = 'alice'")
        assert row["id"] == uid
        assert ALICE_PASSWORD not in tuple(row)
        assert auth.verify_password(ALICE_PASSWORD, row["password_hash"]) is True

    def test_credential_check_pattern(self, users_db):
        seed_user("alice", ALICE_PASSWORD)
        row = db.query_one("SELECT * FROM users WHERE username = 'alice'")
        assert auth.verify_password(ALICE_PASSWORD, row["password_hash"]) is True
        assert auth.verify_password("wrong-pass", row["password_hash"]) is False

    def test_same_password_different_users_get_different_hashes(self, users_db):
        seed_user("alice", ALICE_PASSWORD)
        seed_user("bob", ALICE_PASSWORD)
        rows = db.query_all("SELECT password_hash FROM users ORDER BY username")
        assert rows[0]["password_hash"] != rows[1]["password_hash"]

    def test_rows_land_in_temp_db_only(self, users_db, temp_db_path):
        seed_user("alice", ALICE_PASSWORD)
        assert os.path.exists(temp_db_path)
        assert db.query_one("SELECT COUNT(*) AS n FROM users")["n"] == 1


class TestSessionHelpers:
    """D: login/logout/current semantics on the Flask session (card §3.2)."""

    def test_login_sets_and_current_reads(self, shell):
        with shell.test_request_context():
            auth.login_user(7)
            assert auth.current_user_id() == 7

    def test_anonymous_is_none(self, shell):
        with shell.test_request_context():
            assert auth.current_user_id() is None

    def test_relogin_overwrites_identity(self, shell):
        with shell.test_request_context():
            auth.login_user(1)
            auth.login_user(2)
            assert auth.current_user_id() == 2

    def test_login_keeps_unrelated_session_keys(self, shell):
        with shell.test_request_context():
            session["cart"] = [1]
            auth.login_user(9)
            assert session["cart"] == [1]

    def test_logout_clears_everything(self, shell):
        with shell.test_request_context():
            auth.login_user(5)
            session["cart"] = [1]
            auth.logout_user()
            assert auth.current_user_id() is None
            assert dict(session) == {}

    def test_logout_idempotent_when_anonymous(self, shell):
        with shell.test_request_context():
            auth.logout_user()
            assert auth.current_user_id() is None


class TestLoginRequired:
    """E: the login gate on a dummy protected route (card §7 cases 2–3)."""

    def test_anonymous_gets_302_and_handler_skipped(self, shell):
        client = shell.test_client()
        response = client.get("/protected")
        assert response.status_code == 302
        assert response.headers["Location"] == "/login?next=/protected"
        assert shell.config["HITS"] == []

    def test_nested_path_preserved_in_next(self, shell):
        response = shell.test_client().get("/posts/42/comments")
        assert response.status_code == 302
        assert response.headers["Location"] == "/login?next=/posts/42/comments"

    def test_acceptance_login_hold_logout(self, shell, users_db):
        client = shell.test_client()
        alice_id = seed_user("alice", ALICE_PASSWORD)

        assert client.get(f"/test-login/{alice_id}").status_code == 200
        for _ in range(3):
            response = client.get("/protected")
            assert response.status_code == 200
            assert response.get_json() == {"user_id": alice_id}
        assert shell.config["HITS"] == [alice_id] * 3

        assert client.get("/test-logout").status_code == 200
        response = client.get("/protected")
        assert response.status_code == 302
        assert response.headers["Location"] == "/login?next=/protected"

    def test_tampered_cookie_treated_as_anonymous(self, shell):
        client = shell.test_client()
        response = client.get(
            "/protected", headers={"Cookie": "session=not-a-real-signature"}
        )
        assert response.status_code == 302
        assert response.headers["Location"] == "/login?next=/protected"

    def test_decorated_view_metadata_preserved(self, shell):
        assert shell.view_functions["protected"].__name__ == "protected"


class TestIsolation:
    """F: pure auth logic never touches storage (card §6 mock isolation)."""

    def test_hash_and_session_ops_create_no_db_file(self, shell, temp_db_path):
        stored = auth.hash_password(ALICE_PASSWORD)
        assert auth.verify_password(ALICE_PASSWORD, stored) is True
        with shell.test_request_context():
            auth.login_user(1)
            assert auth.current_user_id() == 1
            auth.logout_user()
        assert not os.path.exists(temp_db_path)
