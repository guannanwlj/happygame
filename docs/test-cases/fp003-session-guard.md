# FP-003 Test Scenarios — Session Management & Protected-Page Access Control

Module under test: `social_app/guard.py` (spec: task card FP-003 §3.2/§6/§7/§8).
Each test builds its own Flask app (minimal `Flask(__name__)` per §6 until
FP-001's `create_app` lands, then preferring it) with a test-only demo
blueprint: `/demo-protected` (behind `login_required`), `/demo-login/<uid>`,
`/demo-logout`, `/demo-whoami`. Seed rows go through `social_app.db` with
`SOCIAL_DB` at a fresh tmp file (card §6: `id=1, username="alice",
password_hash="h"`, plus user 2 for the overwrite case).

## A. Acceptance 1 — unauthenticated access is redirected

| # | Scenario | Expected |
|---|----------|----------|
| A1 | No session, GET demo protected page | 302; `Location` header is exactly the literal `/login` |
| A2 | Logged in (`session["user_id"]=1` via `session_transaction`), GET demo protected page | 200, view body rendered (decorator passes through untouched) |

## B. Acceptance 2 — logout destroys the session

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Logged in as user 1, call `logout_user()` (HTTP demo-logout route), then GET protected page | 302 → `/login`; subsequent `session_transaction` shows no `user_id` key |
| B2 | `logout_user()` on a session holding extra keys | `session.clear()` wipes *all* keys, not just `user_id` |

## C. Acceptance 3 — re-login overwrites the old session

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Old session `user_id=1` exists, call `login_user(2)` | `current_user_id()` returns 2; persisted session value is 2 |
| C2 | C1 driven end-to-end over HTTP (demo-login/2 then demo-whoami) | `/demo-whoami` reports `2` |

## D. Edge cases / contract details

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `current_user_id()` with no session (fresh request context) | Returns `None` (§8 item ④) |
| D2 | `login_user` / `logout_user` inside a `test_request_context` | Primitives operate on the `flask.session` proxy directly (`session["user_id"]` set / cleared); cookie-level persistence is covered end-to-end by B1/C2 |
| D3 | `login_required` metadata | Decorated view keeps `__name__`/`__doc__` (`functools.wraps`) |
| D4 | Redirect target is the literal path, not endpoint reverse-lookup | `Location == "/login"` even though no login route/endpoint is registered anywhere in the test app |
| D5 | GET vs other methods on a protected route (POST unauthenticated) | Still 302 → `/login` (guard is method-agnostic) |

Skeleton/test file: `tests/test_fp003_session_guard.py`.
