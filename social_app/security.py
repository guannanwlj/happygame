"""Password hashing and verification for the social platform (FP-002).

Thin capability layer over ``werkzeug.security`` shared by registration
(FP-005, stores the hash into ``users.password_hash``) and login (FP-006,
compares submitted credentials against the stored hash).

Security rule (task card §3.2): neither these functions nor their callers
may write plaintext passwords to logs or exception messages. This module
therefore never logs and raises no exception that embeds a password.
"""

import werkzeug.security

__all__ = ["check_password", "hash_password"]


def hash_password(plain: str) -> str:
    """Return a salted hash of ``plain`` for storage in ``users.password_hash``.

    Uses ``werkzeug.security.generate_password_hash``; the random salt makes
    each call produce a different string for the same input.
    """
    return werkzeug.security.generate_password_hash(plain)


def check_password(stored_hash: str, plain: str) -> bool:
    """Check ``plain`` against ``stored_hash`` produced by :func:`hash_password`.

    Returns ``True`` on a match, ``False`` otherwise. A stored hash that is
    malformed or uses an unknown method (corrupted/tampered column) also
    yields ``False`` instead of propagating werkzeug's ``ValueError`` — a
    failed comparison, not a crash.
    """
    try:
        return werkzeug.security.check_password_hash(stored_hash, plain)
    except ValueError:
        return False
