"""FP-002 tests: password hashing & verification (social_app/security.py).

Scenarios documented in docs/test-cases/fp002-password-hashing.md.
Function tests call the module directly; users-table scenarios use a fresh
temporary database file through the SOCIAL_DB environment variable.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from social_app import db
from social_app.security import hash_password, verify_password

PLAIN = "s3cret!密码"
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh initialized file so db tests never touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    db.init_db()
    return str(path)


class TestHashIsNotPlaintext:
    """Acceptance 1: stored value is a werkzeug hash, never the plaintext."""

    def test_hash_differs_from_plaintext(self):
        stored = hash_password(PLAIN)
        assert stored != PLAIN
        assert PLAIN not in stored

    def test_hash_format_is_werkzeug_method_string(self):
        stored = hash_password(PLAIN)
        assert stored.startswith("pbkdf2:sha256")

    def test_hash_embeds_salt_and_digest(self):
        method, salt, digest = hash_password(PLAIN).split("$")
        assert method.startswith("pbkdf2:sha256")
        assert salt  # random salt travels inside the string
        assert digest


class TestUsersTableStoresOnlyHash:
    """Acceptance 1 (db side): users.password_hash holds the hash, no plaintext."""

    def test_roundtrip_stores_hash_not_plaintext(self):
        stored = hash_password(PLAIN)
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("alice", stored),
        )
        row = db.query_one("SELECT * FROM users WHERE username = ?", ("alice",))
        assert row is not None
        assert row["password_hash"] == stored
        assert row["password_hash"] != PLAIN
        assert PLAIN not in row["password_hash"]

    def test_users_table_has_no_plaintext_password_column(self):
        columns = {
            r["name"] for r in db.query_all("PRAGMA table_info(users)")
        }
        assert "password_hash" in columns
        assert "password" not in columns
        assert not any("pass" in c for c in columns if c != "password_hash")


class TestVerify:
    """Acceptance 2: correct password verifies, wrong one does not."""

    def test_correct_password(self):
        assert verify_password("right", hash_password("right")) is True

    def test_wrong_password(self):
        assert verify_password("wrong", hash_password("right")) is False

    def test_roundtrip_via_db(self):
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("bob", hash_password("right")),
        )
        row = db.query_one("SELECT password_hash FROM users WHERE username = ?", ("bob",))
        assert verify_password("right", row["password_hash"]) is True
        assert verify_password("wrong", row["password_hash"]) is False


class TestRandomSalt:
    """Acceptance 3: same password hashes twice to two valid, different strings."""

    def test_two_hashes_differ(self):
        assert hash_password(PLAIN) != hash_password(PLAIN)

    def test_both_hashes_verify(self):
        first = hash_password(PLAIN)
        second = hash_password(PLAIN)
        assert first != second
        assert verify_password(PLAIN, first) is True
        assert verify_password(PLAIN, second) is True


class TestEdgeCases:
    """D: empty input, long input, module purity."""

    def test_empty_password_hashes_without_error(self):
        stored = hash_password("")
        assert stored.startswith("pbkdf2:sha256")
        assert verify_password("", stored) is True
        assert verify_password("x", stored) is False

    def test_long_password_roundtrip(self):
        plain = "a" * 5000
        stored = hash_password(plain)
        assert plain not in stored
        assert verify_password(plain, stored) is True
        assert verify_password("a" * 4999, stored) is False

    def test_module_importable_without_flask(self):
        code = (
            "import sys; import social_app.security; "
            "assert not [m for m in sys.modules if m.startswith('flask')]; "
            "print('ok')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"
