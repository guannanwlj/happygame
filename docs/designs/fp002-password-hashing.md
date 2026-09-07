# FP-002 Design: Password Hashing & Verification

Task card: `input/tasks/social-platform/FP-002-password-hashing.task.md`
(sole spec). Goal: `social_app/security.py` exposing the password capability
contract — `hash_password(plain) -> str` and `check_password(stored_hash,
plain) -> bool` — shared by the upcoming FP-005 registration (stores the
hash into `users.password_hash`) and FP-006 login (compares credentials).

## Approach

- New module `social_app/security.py`; a thin, dependency-light wrapper over
  `werkzeug.security.generate_password_hash` /
  `check_password_hash` exactly as mandated by contract §3.2. Werkzeug's
  default method (`scrypt` on this environment, salted and random per call)
  already satisfies every acceptance criterion, so no custom crypto.
- No state, no configuration, no I/O: pure functions, trivially reusable and
  testable. The module performs **no logging at all** and embeds plaintext
  passwords in **no exception message**, honouring the §3.2 constraint. That
  rule is restated in the module docstring so future call sites follow it.
- Compatibility note: on very old werkzeug (<2.0) `generate_password_hash`
  took `method=` inline; we simply call it with defaults, so any modern
  werkzeug works unchanged.

## Key decisions

1. **Thin wrapper, no re-implementation**: the card names werkzeug as the
   underlying primitive; wrapping keeps the seam where FP-005/FP-006 code
   against `social_app.security` (swappable, single audit point).
2. **Malformed stored hash → `False`, not a crash**: werkzeug raises
   `ValueError` when the stored string parses to an unknown method (e.g.
   corrupted/tampered `password_hash` column). `check_password` catches that
   and returns `False` — "credentials do not match" is the correct login-flow
   semantics and prevents a 500 in FP-006. The raised message contains only
   the method name, never the plaintext, so swallowing it leaks nothing.
   Plain `TypeError`/`None`-style programming errors are *not* swallowed.
3. **Salts are left to werkzeug**: two calls with the same plaintext yield
   different strings (random salt) — acceptance 3 — verified by test rather
   than reimplemented.
4. **Out of scope** (per §5): registration/login flows, session management,
   any DB writes. Only one integration smoke test touches `db.py` to prove a
   hash round-trips through the existing `users` table.

## Verification

`python3 -m pytest tests/test_fp002_password.py -q` (plus full suite).
Scenarios documented in `docs/test-cases/fp002-password.md`.
