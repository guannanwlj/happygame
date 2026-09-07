"""FP-002 tests: password hashing & verification (social_app/security.py).

Scenarios documented in docs/test-cases/fp002-password.md. Pure-function
module, so most tests need no fixtures; F2 uses a fresh temp database via
SOCIAL_DB (same pattern as FP-001 tests).
"""

import pytest

from social_app import db
from social_app.security import check_password, hash_password

SEED_PASSWORD = "s3cret!"  # card §6 fixed sample password
WRONG_PASSWORD = "wrong!"  # card §7 wrong-password sample


class TestHashHidesPlaintext:
    """A1–A3: hash output never contains the plaintext and self-verifies."""

    @pytest.mark.parametrize(
        "plain",
        [
            SEED_PASSWORD,
            "pässwörd-中文-🔐",
            "   spaces   everywhere   ",
            "a" * 10_000,
            "!@#$%^&*()[]{};':\",./<>?",
        ],
    )
    def test_hash_excludes_plaintext_and_round_trips(self, plain):
        h = hash_password(plain)
        assert isinstance(h, str) and h
        assert plain not in h
        assert check_password(h, plain) is True


class TestWrongPasswordFails:
    """B1–B3: any password other than the original must fail verification."""

    def test_card_sample_wrong_password(self):
        h = hash_password(SEED_PASSWORD)
        assert check_password(h, WRONG_PASSWORD) is False

    @pytest.mark.parametrize(
        "wrong",
        [
            "S3cret!",  # case change
            "s3cret! ",  # trailing space
            "s3cret",  # substring
            "s3cret!!",  # superstring
            "",
        ],
    )
    def test_near_misses_fail(self, wrong):
        h = hash_password(SEED_PASSWORD)
        assert check_password(h, wrong) is False

    def test_same_length_wrong_password_fails(self):
        h = hash_password(SEED_PASSWORD)
        assert check_password(h, "x" * len(SEED_PASSWORD)) is False


class TestSaltRandomness:
    """C1–C3: same password hashed twice yields distinct, both-valid hashes."""

    def test_two_hashes_differ_and_each_self_verifies(self):
        h1 = hash_password(SEED_PASSWORD)
        h2 = hash_password(SEED_PASSWORD)
        assert h1 != h2
        assert check_password(h1, SEED_PASSWORD) is True
        assert check_password(h2, SEED_PASSWORD) is True
        assert check_password(h1, WRONG_PASSWORD) is False
        assert check_password(h2, WRONG_PASSWORD) is False

    def test_many_hashes_all_distinct(self):
        hashes = {hash_password(SEED_PASSWORD) for _ in range(8)}
        assert len(hashes) == 8


class TestEdgeCasePasswords:
    """D1–D2: empty and very long passwords — no crash, deterministic."""

    def test_empty_password(self):
        h = hash_password("")
        assert check_password(h, "") is True
        assert check_password(h, "x") is False

    def test_very_long_password(self):
        plain = "a" * 100_000
        h = hash_password(plain)
        assert check_password(h, plain) is True
        assert check_password(h, "a" * 99_999) is False


class TestMalformedStoredHash:
    """E1–E2: corrupt stored hash returns False instead of raising."""

    def test_no_separator_garbage(self):
        assert check_password("garbage", SEED_PASSWORD) is False

    def test_unknown_method(self):
        # Raw werkzeug raises ValueError('Invalid hash method ...') here;
        # the wrapper must translate it to a plain False.
        assert check_password("bogus:1:2$aa$bb", SEED_PASSWORD) is False


class TestContractAndStorage:
    """F1–F2: card §3.2 contract surface + round-trip through users table."""

    def test_module_exports_contract_functions(self):
        import social_app.security as security

        assert callable(security.hash_password)
        assert callable(security.check_password)

    def test_hash_round_trips_through_users_table(self, tmp_path, monkeypatch):
        monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "social_platform.db"))
        db.init_db()
        stored = hash_password(SEED_PASSWORD)
        cur = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("alice", stored),
        )
        row = db.query_one(
            "SELECT password_hash FROM users WHERE id = ?", (cur.lastrowid,)
        )
        assert row["password_hash"] == stored  # survives storage verbatim
        assert check_password(row["password_hash"], SEED_PASSWORD) is True
        assert check_password(row["password_hash"], WRONG_PASSWORD) is False
