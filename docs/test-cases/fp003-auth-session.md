# FP-003 Test Scenarios — Authentication & Session Management

Module under test: `social_app/auth.py` (domain), `social_app/routes.py`
(HTTP), `social_app/app.py` (factory). Spec: self-built contract in
`docs/designs/fp003-auth-session.md` (task card absent from checkout).
All DB-backed tests use a fresh temp file via `SOCIAL_DB` (FP-001 pattern).

## A. Password hashing primitives

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `hash_password` then `verify_password` with the right password | Hash is a non-empty string ≠ plaintext; verify → True |
| A2 | `verify_password` with a wrong password | False (not an exception) |
| A3 | Hash the same password twice | Hashes differ (random salt); both verify True |
| A4 | Hash format | Starts with `method:params$salt$hash` style prefix (`^[a-z0-9]+:`), never contains the plaintext |

## B. Input validation

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Valid username (`alice_01`) and boundary lengths (3, 32 chars) | Accepted |
| B2 | Username too short (2), too long (33), empty | `ValidationError` |
| B3 | Username with space / `-` / unicode / non-string (int, None) | `ValidationError` |
| B4 | Password boundary lengths (8, 128 ok; 7, 129 fail); non-string | `ValidationError` |

## C. Registration (real DB)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `register_user("alice", pw)` | Returns row with id/username/created_at; DB hash verifies pw; plaintext absent from DB |
| C2 | Register same username twice | Second raises `UsernameTakenError`; users table still has exactly 1 row |
| C3 | `register_user("Alice", pw)` when `alice` exists | Succeeds — usernames case-sensitive |
| C4 | Validation runs before insert | Invalid input leaves users table empty |

## D. Authentication (real DB)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Correct username + password | Returns the stored user row (id, username) |
| D2 | Correct username, wrong password | `InvalidCredentialsError` |
| D3 | Unknown username | `InvalidCredentialsError` (same type as D2 — no enumeration) |
| D4 | Empty-string username or password | `InvalidCredentialsError` |

## E. Session helpers (dict mock — no Flask)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `login_session(sess, uid)` | `sess["user_id"] == uid` |
| E2 | Session with stale keys (`{"cart": 1, "user_id": 99}`), then login | Old keys/values gone, only new `user_id` remains (fixation mitigation) |
| E3 | Login as alice then as bob | `session_user_id` reports bob only |
| E4 | `logout_session(sess)` | Mapping empty afterwards; idempotent on empty dict |
| E5 | `session_user_id` on empty/anonymous dict | `None` |
| E6 | `current_user(sess)` | Row for live user; `None` when anonymous; `None` when the user row was deleted |

## F. HTTP API — register (test client)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | POST /auth/register valid JSON | 201; body `{"id","username"}`; row present in DB with verifiable hash |
| F2 | Duplicate username | 409 `{"error": ...}` |
| F3 | Invalid username (bad chars / short) | 400 with `error` message |
| F4 | Short password | 400 |
| F5 | Missing field (no password / no username) | 400 |
| F6 | Wrong content type (`text/plain`) | 415 JSON error |
| F7 | Malformed JSON body | 400 JSON error |
| F8 | Response leaks nothing | No `password` / `password_hash` key in any response |

## G. HTTP API — login / logout / me (test client)

| # | Scenario | Expected |
|---|----------|----------|
| G1 | Login with correct credentials | 200 `{"id","username"}`; `Set-Cookie` header issued |
| G2 | GET /auth/me with the session cookie | 200 `{"id","username"}` matching the logged-in user |
| G3 | Login wrong password | 401 JSON `error` |
| G4 | Login unknown user | 401 — identical status and body shape as G3 |
| G5 | GET /auth/me without login | 401 JSON `error` |
| G6 | Login, logout, then GET /auth/me | Logout 200 `{"ok": true}`; me → 401 |
| G7 | Logout without prior login | 200 (idempotent) |
| G8 | Login alice, then login bob on same client | /auth/me reports bob (session replaced) |
| G9 | Register + login round trip | 201 then 200 with same id/username; DB row count 1 |

## H. `login_required` decorator

| # | Scenario | Expected |
|---|----------|----------|
| H1 | Protected route, anonymous request | 401 JSON `{"error": "authentication required"}`; handler not invoked |
| H2 | Protected route after login | Handler invoked with `user_id=` kwarg; 200 echo |

## I. App factory (embedded FP-002 contract)

| # | Scenario | Expected |
|---|----------|----------|
| I1 | `create_app()` | Returns Flask app; the four auth rules exist in `url_map` |
| I2 | Config overrides dict | Applied (`SECRET_KEY`, `TESTING`) |
| I3 | `$SOCIAL_APP_SECRET_KEY` env set (no overrides) | Used as `SECRET_KEY`; unset → non-empty dev fallback |
| I4 | Unknown URL / wrong method | JSON error body (no HTML), 404 / 405 |
| I5 | Factory initializes schema | `users` table exists in the `SOCIAL_DB` file after `create_app()` |

## M. Mock isolation (routes decoupled from domain/DB)

| # | Scenario | Expected |
|---|----------|----------|
| M1 | Monkeypatch `routes.register_user` with a spy + canned row | Endpoint returns 201 with the canned row's fields; spy called once with parsed `(username, password)` |
| M2 | Monkeypatch `routes.register_user` to raise `UsernameTakenError` | 409; no DB file rows involved |
| M3 | Monkeypatch `routes.register_user` to raise `ValidationError` | 400 with the message |
| M4 | Monkeypatch `routes.authenticate` to raise `InvalidCredentialsError` | 401 without any DB access |

Skeleton/test file: `tests/test_fp003_auth_session.py`.
