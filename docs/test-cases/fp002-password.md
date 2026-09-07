# FP-002 Test Scenarios — Password Hashing & Verification

Module under test: `social_app/security.py` (spec: task card FP-002 §3.2/§7/§8).
Pure-function module — no shared state between tests. Seed data per card §6:
fixed sample password `s3cret!` (hash generated at runtime; wrong password
`wrong!`).

## A. Acceptance 1 — hash hides plaintext, self-verifies (card §7 GWT-1)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `hash_password("s3cret!")` | Returns non-empty str that does **not** contain the plaintext `s3cret!` as a substring |
| A2 | `check_password(hash_of_s3cret, "s3cret!")` | `True` |
| A3 | Same round-trip for a spread of inputs (unicode, spaces, punctuation, long) | Plaintext never a substring of its hash; `check_password` round-trip `True` for each |

## B. Acceptance 2 — wrong password fails (card §7 GWT-2)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `check_password(hash_of("s3cret!"), "wrong!")` | `False` |
| B2 | Near-miss passwords (case change, trailing space, substring, superstring) | `False` for each |
| B3 | Correct-length but wrong password of same charset | `False` |

## C. Acceptance 3 — salt randomness (card §7 GWT-3)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `hash_password("s3cret!")` twice | The two hash strings differ |
| C2 | Each of the two hashes | Self-verifies against `"s3cret!"` (`True`) and rejects `"wrong!"` (`False`) |
| C3 | Many repeated hashes of one password | All pairwise distinct (no salt reuse collapse) |

## D. Edge cases — empty / very long passwords (card §8 ④)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `hash_password("")` then `check_password(h, "")` / `check_password(h, "x")` | No crash; `True` / `False` — deterministic behaviour |
| D2 | Very long password (100_000 chars) hashed and verified | No crash; self-verify `True`; off-by-one wrong password `False` |

## E. Error handling — corrupt/malformed stored hash (design decision 2)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `check_password("garbage", "s3cret!")` (no separator) | `False`, no exception |
| E2 | `check_password("bogus:1:2$aa$bb", "s3cret!")` (unknown method) | `False`, no exception (raw werkzeug would raise `ValueError`) |

## F. Contract & storage round-trip

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Import surface | Module exports exactly the card §3.2 names `hash_password` / `check_password` as callables |
| F2 | Store `hash_password("s3cret!")` in `users.password_hash` via `social_app.db`, read it back | Stored string survives verbatim; `check_password(stored, "s3cret!")` is `True`, with `"wrong!"` `False` — the FP-005/FP-006 usage pattern |

Skeleton/test file: `tests/test_fp002_password.py`.
