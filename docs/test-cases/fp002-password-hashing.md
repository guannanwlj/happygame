# FP-002 Test Scenarios — Password Hashing & Verification

Module under test: `social_app/security.py` (spec: task card FP-002 §4/§7/§8).
Function-level tests run against plain calls; the users-table scenarios use a
fresh temporary DB file via the `SOCIAL_DB` env var (`db.init_db()` first) per
card §6 — no repo pollution.

## A. Acceptance 1 — stored value is a hash, never plaintext

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `hash_password("s3cret!密码")` (unicode mix) | Output ≠ plaintext and does not contain the plaintext as a substring |
| A2 | Format of the output | Werkzeug method string containing `pbkdf2:sha256`, with embedded salt and digest segments (self-contained) |
| A3 | Hash written to `users.password_hash` via `db.execute`, row read back | Stored value equals the hash, differs from and does not contain the plaintext |
| A4 | Column set of the `users` table | No plaintext password column exists (only id/username/password_hash/created_at from FP-001) |

## B. Acceptance 2 — verification compares correctly

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `verify_password("right", hash_password("right"))` | `True` |
| B2 | `verify_password("wrong", hash_password("right"))` | `False` |
| B3 | Full DB roundtrip: store `hash_password("right")`, read the row, verify against the stored column | `"right"` → `True`, `"wrong"` → `False` |

## C. Acceptance 3 — random salt, both outputs valid

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `hash_password(p)` called twice with the same `p` | Two different outputs (random salt) |
| C2 | Both outputs from C1 checked with `verify_password(p, ...)` | Both `True` (salt travels inside the hash string) |

## D. Edge cases / contract

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `hash_password("")` | No exception; output still a `pbkdf2:sha256` method string |
| D2 | Verify against `hash_password("")` | `""` → `True`; any non-empty guess → `False` (deterministic behavior for empty input) |
| D3 | Long password (5000 chars) roundtrip | Hashes and verifies `True`; plaintext absent from the hash |
| D4 | Import `social_app.security` in a fresh interpreter | Succeeds without Flask ever entering `sys.modules` (§4 purity contract) |

Skeleton/test file: `tests/test_security.py`.
