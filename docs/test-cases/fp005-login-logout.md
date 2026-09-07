# FP-005 Test Scenarios — 用户登录与登出 (Login & Logout)

Under test: `social_app/login.py` (routes `GET/POST /login`, `POST /logout`)
plus the FP-003 stand-in contract `social_app/auth.py` and the minimal shell
`social_app/app.py` (card §3/§6). Spec: task card FP-005 §4/§7/§8.

Fixtures: fresh temp DB via `SOCIAL_DB`; seed user `alice` with
`hash_password("alice-pass-123")` (card §6, direct INSERT replacing FP-004);
a dummy protected route `/whoami` (`@login_required`) to observe login state;
Flask test client keeps the session cookie across requests.

## A. Acceptance 1 — correct credentials establish a session

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `GET /login` | 200; page contains the form (用户名/密码 fields, POST target `/login`) |
| A2 | `GET /login?next=/posts` | Form carries hidden `next=/posts` through to the POST |
| A3 | `POST /login` alice + correct password | 302 to `/` ; `session["user_id"] == alice.id` (login state) |
| A4 | After A3, `GET /whoami` on same client | 200 with alice's id (`current_user_id()` in a request context) |
| A5 | `POST /login` with `next=/posts` | 302 to `/posts` |

## B. Acceptance 2 — wrong credentials: error, no session

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Non-existent username | 200 re-render with 「用户名或密码错误」; session has no `user_id`; `/whoami` still 302 → `/login?next=/whoami` |
| B2 | Existing username, wrong password | Same as B1 |
| B3 | Empty username, correct-shaped form | Same unified error, no session |
| B4 | Missing `password` field entirely | Same unified error, no session (no KeyError) |
| B5 | Username with different case (`Alice`) | Same unified error (exact-match lookup), no session |
| B6 | User whose stored `password_hash` is garbage | Same unified error, no session, no 500 (fail-closed verify) |
| B7 | Failed login then correct login on same client | Failure page first, then success 302 + session established |

## C. Acceptance 3 — logout destroys the session

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Login, then `POST /logout` | 302 to `/login`; session cleared (no `user_id`) |
| C2 | After C1, `GET /whoami` | 302 → `/login?next=/whoami` (must re-login) |
| C3 | `POST /logout` without a session | Still 302 to `/login`, no error (idempotent) |

## D. `next` redirect safety (open-redirect hardening)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `next=http://evil.com` on successful login | Redirect to `/`, not the external URL |
| D2 | `next=//evil.com` (protocol-relative) | Redirect to `/` |
| D3 | `next=friends` (no leading `/`) | Redirect to `/` |
| D4 | `next=` (empty) / absent | Redirect to `/` |

## E. Auth stand-in contract (`social_app/auth.py`, FP-003 §3.2)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `hash_password` → `verify_password` roundtrip | Hash verifies `True` for the right password |
| E2 | Same password hashed twice | Different stored strings (random salt); both verify `True` |
| E3 | Wrong password / malformed stored strings (`""`, `"garbage"`, wrong algo tag, bad hex, truncated fields) | `verify_password` returns `False`, never raises |
| E4 | `login_user`/`logout_user`/`current_user_id` in a request context | `None` → set id → `None` after clear |
| E5 | `login_required` anonymous request | 302 to `/login?next=<original path>` (observed via `/whoami`) |
| E6 | `login_required` authenticated request | View executes (observed via `/whoami` = 200) |

Skeleton/test file: `tests/test_fp005_login.py`.
