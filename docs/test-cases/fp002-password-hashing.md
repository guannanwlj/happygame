# FP-002 Test Scenarios — Password Secure Storage

Module under test: `social_app/security.py::hash_password` /
`verify_password` (spec: task card FP-002 §3.2 / §7 / §8). Pure string
functions, stdlib only, no DB and no web.

Seed data (card §6): `"secret123"` (correct) and `"wrong-password"`
(incorrect). Hashes are generated at test time via `hash_password`.

## A. Acceptance — card §7

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `hash_password("secret123")` | result `!= "secret123"` (not plaintext) |
| A2 | Two `hash_password` calls on the same plaintext | the two strings differ (salt is random) |
| A3 | Same password hashed twice, both hashes verified with the plaintext | both `verify_password` return `True` (cross-check) |
| A4 | Correct vs wrong plaintext against one stored hash | `"secret123"` → `True`; `"wrong-password"` → `False` |
| A5 | `verify_password` on `""`, `"not-a-hash"`, unknown algorithm | `False`, no exception raised |
| A6 | Parse a produced hash | prefix `pbkdf2_sha256$`, exactly four `$`-separated segments: algorithm, iterations, hex salt, hex digest |

## B. Hash shape and algorithm

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Split hash on `$` | 4 parts; part 0 == `pbkdf2_sha256`; part 1 is a positive int; parts 2/3 are valid hex |
| B2 | Recompute PBKDF2 from parsed salt/iterations | equals the parsed digest (documents the exact algorithm and cost) |
| B3 | Salt segment decoded | 16 bytes (`secrets.token_bytes(16)`) |
| B4 | Iterations segment | equals the module constant (200000) and is > 0 |
| B5 | Non-ASCII password (`"密码pä55"`) | round-trips: hash then verify returns `True` (UTF-8) |
| B6 | Empty plaintext `""` | hashes to a non-empty string and verifies `True` (no policy here) |

## C. Verification semantics

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Hash from stored cost is used | a hash with a *different* iteration count still verifies if recomputed with that stored cost (upgrade-friendly) |
| C2 | Password hashed for A, verified against B's hash | `False` (no cross-user collision) |
| C3 | `stored` is `None` / `123` (non-string) | `False`, no exception (defensive) |
| C4 | Wrong password against many stored hashes | always `False` |

## D. Malformed / hostile `stored` — must not crash

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `""` empty string | `False` |
| D2 | `"not-a-hash"` (seed) | `False` |
| D3 | `"md5$1000$aa$bb"` (unknown algorithm) | `False` |
| D4 | `"pbkdf2_sha256$1000$aa"` (too few segments) | `False` |
| D5 | `"pbkdf2_sha256$1000$aa$bb$cc"` (too many segments) | `False` |
| D6 | `"pbkdf2_sha256$notanint$aa$bb"` (bad iterations) | `False` |
| D7 | `"pbkdf2_sha256$0$aa$bb"` (zero iterations) | `False` |
| D8 | `"pbkdf2_sha256$-1$aa$bb"` (negative iterations) | `False` |
| D9 | `"pbkdf2_sha256$1000$nothex$bb"` (bad salt hex) | `False` |
| D10 | `"pbkdf2_sha256$1000$aa$zz"` (bad digest hex) | `False` |
| D11 | Digest of arbitrary/odd length (`"pbkdf2_sha256$1000$aa$abcd"`) | `False` (compare_digest mismatch, no raise) |
| D12 | Leading/trailing `$` or whitespace variants | `False`, no raise |
| D13 | Every malformed case | returns a real `bool` (`is False`), never raises |

## E. Contract shape sanity

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `hash_password` return type | `str`, non-empty |
| E2 | `verify_password` return type | `bool` instance in both the hit and miss case |

Test file: `tests/test_fp002_password.py`.
