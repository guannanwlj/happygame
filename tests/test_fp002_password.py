"""FP-002 tests: password secure storage (social_app.security).

Scenarios documented in docs/test-cases/fp002-password-hashing.md. The module
under test is pure: str in -> str / bool out, stdlib only, no DB and no web.
"""

import hashlib
import secrets

import pytest

from social_app.security import ITERATIONS, hash_password, verify_password

PLAIN = "secret123"
WRONG = "wrong-password"


def stored_hash(plain=PLAIN):
    """Card §6 seed: produce a stored hash string for later verification."""
    return hash_password(plain)


class TestHashingAcceptance:
    """A1–A3, B1, E1: hash output is opaque, salted and self-describing."""

    def test_hash_is_not_plaintext(self):
        assert stored_hash() != PLAIN

    def test_same_plaintext_hashes_differently(self):
        assert stored_hash() != stored_hash()

    def test_hash_verifies_for_both_salts(self):
        first, second = stored_hash(), stored_hash()
        assert verify_password(PLAIN, first) is True
        assert verify_password(PLAIN, second) is True

    def test_hash_is_a_stripped_four_part_string(self):
        stored = stored_hash()
        assert isinstance(stored, str)
        assert stored
        assert stored == stored.strip()
        parts = stored.split("$")
        assert len(parts) == 4
        assert parts[0] == "pbkdf2_sha256"

    def test_iterations_segment_is_positive_int(self):
        algorithm, iterations, salt_hex, digest_hex = stored_hash().split("$")
        assert int(iterations) > 0
        assert len(bytes.fromhex(salt_hex)) == 16
        assert bytes.fromhex(digest_hex)
        assert algorithm == "pbkdf2_sha256"


class TestAlgorithm:
    """B2–B6: exact PBKDF2-HMAC-SHA256 contract, UTF-8 and constant cost."""

    def test_digest_matches_manual_pbkdf2(self):
        algorithm, iterations, salt_hex, digest_hex = stored_hash().split("$")
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            PLAIN.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        assert derived.hex() == digest_hex

    def test_iterations_constant_is_200000(self):
        assert ITERATIONS == 200_000

    def test_hash_uses_the_module_iteration_constant(self):
        assert stored_hash().split("$")[1] == str(ITERATIONS)

    def test_non_ascii_password_round_trips(self):
        plain = "密码pä55"
        assert verify_password(plain, hash_password(plain)) is True

    def test_empty_password_hashes_and_verifies(self):
        stored = hash_password("")
        assert stored != ""
        assert stored != "pbkdf2_sha256$$$"
        assert verify_password("", stored) is True

    def test_stored_cost_is_used_not_the_constant(self):
        """C1: an old hash with a different cost still verifies (upgrade-safe)."""
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac(
            "sha256", PLAIN.encode("utf-8"), salt, 1000
        )
        legacy = f"pbkdf2_sha256$1000${salt.hex()}${derived.hex()}"
        assert verify_password(PLAIN, legacy) is True


class TestVerifySemantics:
    """A4, C2–C4: correct/incorrect plaintext and cross-hash checks."""

    def test_correct_password_is_true_and_wrong_is_false(self):
        stored = stored_hash()
        assert verify_password(PLAIN, stored) is True
        assert verify_password(WRONG, stored) is False

    def test_password_does_not_verify_against_another_hash(self):
        assert verify_password(PLAIN, stored_hash(WRONG)) is False

    def test_hash_verifies_only_after_many_trials_of_wrong(self):
        stored = stored_hash()
        assert all(
            verify_password(candidate, stored) is False
            for candidate in ("", WRONG, PLAIN + "x", PLAIN[:-1])
        )

    def test_verify_returns_bool_for_non_string_stored(self):
        assert verify_password(PLAIN, None) is False
        assert verify_password(PLAIN, 123) is False


class TestMalformedStored:
    """A5, D1–D13: malformed or unknown hashes return False, never raise."""

    @pytest.mark.parametrize(
        "stored",
        [
            "",  # D1 empty
            "not-a-hash",  # D2 seed
            "md5$1000$aa$bb",  # D3 unknown algorithm
            "pbkdf2_sha1$1000$aa$bb",  # D3 unknown algorithm variant
            "pbkdf2_sha256$1000$aa",  # D4 too few segments
            "pbkdf2_sha256$1000$aa$bb$cc",  # D5 too many segments
            "pbkdf2_sha256$notanint$aa$bb",  # D6 bad iterations
            "pbkdf2_sha256$0$aa$bb",  # D7 zero iterations
            "pbkdf2_sha256$-1$aa$bb",  # D8 negative iterations
            "pbkdf2_sha256$1000$nothex$bb",  # D9 bad salt hex
            "pbkdf2_sha256$1000$aa$zz",  # D10 bad digest hex
            "pbkdf2_sha256$1000$aa$abcd",  # D11 short digest, no raise
            "pbkdf2_sha256$1000$abc$cc",  # odd-length salt hex
            "$pbkdf2_sha256$1000$aa$bb",  # D12 leading separator
            "pbkdf2_sha256$1000$aa$bb$",  # D12 trailing separator
            "  pbkdf2_sha256$1000$aa$bb  ",  # D12 whitespace wrapper
        ],
    )
    def test_malformed_stored_returns_false(self, stored):
        assert verify_password(PLAIN, stored) is False

    def test_malformed_and_wrong_passwords_never_raise(self):
        for stored in ("", "not-a-hash", "pbkdf2_sha256$x$y$z"):
            assert verify_password(WRONG, stored) is False


class TestResultShape:
    """E1, E2: return types are stable."""

    def test_hash_password_returns_non_empty_str(self):
        result = hash_password(PLAIN)
        assert isinstance(result, str)
        assert result

    def test_verify_password_returns_bool_on_hit_and_miss(self):
        stored = stored_hash()
        assert verify_password(PLAIN, stored) is True
        assert verify_password(WRONG, stored) is False
