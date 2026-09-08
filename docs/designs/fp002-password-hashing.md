# FP-002 Design: Password Hashing & Verification

Task card: `input/tasks/social-media-platform/FP-002-password-hashing.task.md`
(sole spec). Goal: pure-function module `social_app/security.py` exposing
`hash_password(plain) -> str` and `verify_password(plain, stored_hash) -> bool`
so FP-004 (registration) stores only `password_hash` and FP-005 (login)
compares against it — no plaintext password on any path (strategic red line).

## Approach

- New module `social_app/security.py`, no other files touched. It imports only
  `werkzeug.security` — no Flask request context, no database access, no
  validation of empty inputs (caller FP-004's job per card §4).
- `hash_password` = `werkzeug.security.generate_password_hash(plain,
  method=METHOD)` with module constant `METHOD = "pbkdf2:sha256"`.
- `verify_password` = `werkzeug.security.check_password_hash(stored_hash,
  plain)` (werkzeug's argument order is hash-first; our public signature stays
  `(plain, stored_hash)` exactly as the card's contract §4 specifies).

## Key decisions

1. **Method passed explicitly, not relied on werkzeug's default.** The card
   describes `pbkdf2:sha256` as the default, which was true for werkzeug < 2.3;
   the installed werkzeug 3.1.8 defaults to `scrypt:32768:8:1`. Acceptance §7
   requires the stored string to contain `pbkdf2:sha256`, so pinning the method
   keeps the output format deterministic across werkzeug versions.
2. **Self-contained hash strings.** werkzeug output embeds method, iterations,
   salt, and digest (`pbkdf2:sha256:<iters>$<salt>$<digest>`), so
   `verify_password` needs nothing beyond the stored column — no separate salt
   column, no schema change (card §3.1: no DDL in this task).
3. **Thin wrappers only.** No try/except around werkzeug calls: the card
   defines no error paths for this module, and masking werkzeug's own
   ValueError on malformed stored hashes would hide caller bugs (corrupt rows
   are FP-005's concern).
4. **DB stays out.** Persisting the hash is the caller's job; tests exercise
   the users-table roundtrip through the existing `social_app/db.py` API with
   `SOCIAL_DB` pointed at a tmp file (card §6), not through any new write path
   in this module.
5. **Purity is testable.** A subprocess test imports `social_app.security` in
   a fresh interpreter and asserts `flask` never enters `sys.modules`,
   enforcing the §4 contract "no Flask request context, independently
   importable".

## Verification

`python3 -m pytest tests/test_security.py -q` (plus the full suite).
Scenarios documented in `docs/test-cases/fp002-password-hashing.md`.
