"""Password hashing primitives (FP-002).

Thin wrappers around werkzeug's PBKDF2 implementation so that registration
(FP-004) stores only ``users.password_hash`` and login (FP-005) compares
against it. Plain passwords never persist on any path (strategic red line).

Pure functions: no Flask request context, no database access, no input
validation — callers own those concerns (task card §4).
"""

from werkzeug.security import check_password_hash, generate_password_hash

METHOD = "pbkdf2:sha256"


def hash_password(plain: str) -> str:
    """Return a self-contained ``method$salt$digest`` hash string for ``plain``.

    The salt is random, so two calls with the same input differ; everything a
    later verification needs travels inside the returned string.
    """
    return generate_password_hash(plain, method=METHOD)


def verify_password(plain: str, stored_hash: str) -> bool:
    """Re-hash ``plain`` with the salt embedded in ``stored_hash`` and compare."""
    return check_password_hash(stored_hash, plain)
