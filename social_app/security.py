"""Password secure storage (FP-002).

Irreversible password hashing/verification primitives consumed by
registration (FP-007) and login (FP-009). Stdlib only, pure string in/out:
no database and no web code here.

The stored string is self-describing so the algorithm, cost and random salt
travel with the digest and can be upgraded later without a schema change:

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
"""

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000
SALT_BYTES = 16


def hash_password(plain: str) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash string for ``plain``.

    A fresh ``secrets.token_bytes(16)`` salt is drawn on every call, so the
    same plaintext hashes to a different string each time and identical
    passwords are not detectable from the stored column.
    """
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, ITERATIONS
    )
    return f"{ALGORITHM}${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """Return True iff ``plain`` matches the hash in ``stored``.

    Verification uses the cost recorded inside ``stored`` (not the current
    module constant), so raising ``ITERATIONS`` later still validates old
    hashes. Fails closed: any malformed/unknown ``stored`` or non-string
    input returns False instead of raising, so callers can treat this as a
    plain boolean gate.
    """
    if not isinstance(stored, str):
        return False
    parts = stored.split("$")
    if len(parts) != 4:
        return False
    algorithm, iterations_text, salt_hex, digest_hex = parts
    if algorithm != ALGORITHM:
        return False
    try:
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (TypeError, ValueError):
        return False
    if iterations <= 0:
        return False
    try:
        candidate = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), salt, iterations
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return hmac.compare_digest(candidate, expected)
