# FP-002 Design: Password Secure Storage

Task card: `input/tasks/social-platform-mvp/FP-002-password-hashing.task.md`
(sole spec, embedded in the work order). Goal: the irreversible password
hash/verify capability in a new module `social_app/security.py`, consumed by
registration (FP-007) and login (FP-009). No DB and no web code here.

## Approach

- One new module `social_app/security.py`, stdlib only (`hashlib`, `secrets`,
  `hmac`). Nothing else touched; the existing `users.password_hash` column
  (already in `social_app/db.py`) just stores the string this module returns.
- Public contract (card §3.2):

  ```python
  def hash_password(plain: str) -> str
  def verify_password(plain: str, stored: str) -> bool
  ```

- **Self-describing hash string** — four `$`-separated fields so the
  algorithm, cost and salt travel with the digest and can be upgraded later
  without a schema change:

  ```
  pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
  ```

- **Hashing** — a fresh `secrets.token_bytes(16)` salt on every call, then
  `hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)`
  with the module constant `ITERATIONS = 200_000`. The same plaintext hashes
  to a different string each time (random salt), so identical passwords are
  not detectable from the stored column.
- **Verification** — parse `stored` back into algorithm / iterations / salt /
  digest, recompute with the *stored* salt and cost, and compare with
  `hmac.compare_digest`. Returns `False` (never raises) for any malformed or
  unknown input, so callers can treat it as a plain boolean gate.

## Key decisions

1. **Fail closed, never raise** — `verify_password` wraps parsing/decoding in
   a single guarded path and returns `False` on empty/non-string `stored`,
   wrong field count, unknown algorithm, non-positive/unparsable iterations,
   non-hex salt/digest, or a failed comparison. This matches card §7's
   「格式非法或算法不识别时返回 False，不抛异常」 and keeps login/registration
   free of try/except around the call.
2. **Iterations live in the string, not in verify** — verification uses the
   cost recorded in `stored`, not the current module constant, so raising
   `ITERATIONS` later still validates old hashes. `hash_password` is the only
   place the constant is applied.
3. **Constant-time comparison** — `hmac.compare_digest` is used for the
   digest check to avoid leaking match length via timing. Both operands are
   `bytes`.
4. **Explicit prefix/algorithm whitelist** — only `pbkdf2_sha256` is accepted;
   any other algorithm segment returns `False` rather than attempting a guess.
   The card fixes the algorithm, so no negotiation is needed.
5. **UTF-8 encoding** — `plain.encode("utf-8")` exactly as the card dictates,
   so non-ASCII passwords round-trip.
6. **No truncation / no policy checks here** — empty strings, length,
   strength, and username binding are FP-007's concern; this module only
   hashes whatever bytes it is given. Locked so later features add policy
   deliberately rather than by drift.

## Verification

`python3 -m pytest tests/test_fp002_password.py -q` (plus the full suite).
Scenarios documented in `docs/test-cases/fp002-password-hashing.md`.
