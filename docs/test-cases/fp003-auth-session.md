# FP-003 Test Scenarios — Authentication & Session Management

Module under test: `social_app/auth.py` only (card §4). Spec: task card
`input/tasks/social-platform/FP-003-auth-session.task.md` §3.2 (contract),
§6 (mock/seed strategy), §7 (acceptance). DB-backed groups use a fresh temp
file via `SOCIAL_DB` + the real FP-001 `db` module; HTTP groups use a
test-local minimal Flask shell (FP-002 absent — card §6).

## A. Password hashing primitives (card §7 case 1)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `hash_password(pw)` output format | Matches `pbkdf2:sha256$<int>$<32 hex>$<64 hex>` exactly; never contains the plaintext |
| A2 | Round trip: hash then `verify_password(pw, stored)` | True |
| A3 | Wrong plaintext against a valid stored hash | `False` (not an exception) |
| A4 | Same password hashed twice | Hashes differ (random salt); both verify True |
| A5 | Plaintext never at rest | stored hash `!=` plaintext (subsumed by A1 but asserted directly) |

## B. `verify_password` robustness (edge / error paths)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Empty stored string / arbitrary garbage | `False` |
| B2 | Wrong field count (3 or 5 `$`-parts) | `False` |
| B3 | Unknown method token (`scrypt$...`) | `False` |
| B4 | Non-numeric / zero / negative iteration count | `False` (no crash, no KDF run) |
| B5 | Absurdly large iteration count | `False` before any KDF work (CPU guard) |
| B6 | Non-hex salt or digest fields | `False` |
| B7 | Non-string `stored` (int/None/list) | `False`, no exception |
| B8 | Correct hash but one hex char of digest flipped | `False` |

## C. Credential storage round trip (real FP-001 DB, seed per card §6)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Seed user `alice` with `hash_password("alice-pass-123")` | Row stored; `password_hash` column verifies the password; plaintext absent from the whole row |
| C2 | Credential check pattern: fetch by username, `verify_password(plain, row["password_hash"])` | True for the right password |
| C3 | Same pattern with a wrong password | False → caller would refuse login |
| C4 | Two seeded users, same password | Stored hashes differ (per-user salt) |

## D. Session helpers (minimal Flask shell; card §3.2 semantics)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `login_user(uid)` | `current_user_id() == uid` |
| D2 | Fresh session, no login | `current_user_id() is None` |
| D3 | `login_user` twice (alice then bob) | Second id wins (plain overwrite) |
| D4 | `login_user` keeps unrelated session keys | Card: only sets `user_id` (no clear) |
| D5 | `logout_user()` | `current_user_id() is None`; session emptied |
| D6 | `logout_user()` when already anonymous | No error (idempotent via `session.clear()`) |

## E. `login_required` gate (card §7 cases 2–3; dummy protected route)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Anonymous GET `/protected` | 302; `Location: /login?next=/protected`; handler not invoked |
| E2 | Anonymous GET nested path `/posts/42/comments` | `Location: /login?next=/posts/42/comments` |
| E3 | Acceptance flow: `login_user(alice_id)` → revisit protected route | 200 (session held across requests — cookie jar = 会话保持期), handler sees alice's id |
| E4 | Continuation: several further requests while logged in | Still 200 — no repeated login needed |
| E5 | `logout_user()` then revisit | Back to 302 intercept (needs re-login) |
| E6 | Tampered/unsigned session cookie | Treated as anonymous → 302 |
| E7 | Decorated view metadata | `__name__`/`__doc__` preserved (`functools.wraps`) |

## F. Isolation (card §6 mock strategy)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Hash/verify/session groups run with no DB file created | `social_app` never touches storage for pure auth logic |
| F2 | DB groups never touch the repo default `social_platform.db` | All rows land in the `SOCIAL_DB` tmp file |

Skeleton/test file: `tests/test_fp003_auth.py` (card §8 name).
