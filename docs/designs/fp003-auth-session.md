# FP-003 Design: Authentication & Session Management

Task card: `input/tasks/social-platform/FP-003-auth-session.task.md` — **the file is
not present in this checkout** (FP-002 is also unmerged). Per the task spec's
fallback rule ("未合入时按任务卡 §3 内嵌契约自建，勿等待"), this design
self-builds the contract from the FP-001 foundation (`social_app/db.py`, DDL in
`docs/designs/fp001-data-model-storage.md`) and the standard social-platform
auth split. Everything the missing card would have fixed is listed under
"Self-built contract" below so a later card can be reconciled against it.

Goal: username/password authentication plus cookie-session management on top of
the FP-001 `users` table (which already stores `password_hash` only — D-004).

## Self-built contract (embedded, replaces missing card §3)

- **Domain layer** `social_app/auth.py`, no Flask imports:
  - `hash_password(pw)` / `verify_password(hash, pw)` — werkzeug
    `generate_password_hash` / `check_password_hash`, default method
    (scrypt:32768:8:1, ~65 ms/op on this machine).
  - Input rules: username 3–32 chars of `[A-Za-z0-9_]`; password 8–128 chars;
    both must be `str`. Usernames are case-sensitive (`UNIQUE` default
    collation).
  - `register_user(username, password)` → user row; errors:
    `ValidationError` (input), `UsernameTakenError` (duplicate).
  - `authenticate(username, password)` → user row; `InvalidCredentialsError`
    for unknown user *and* wrong password (same error → no user enumeration).
  - `get_user(user_id)` → row or `None`.
  - Session helpers operating on any mutable mapping (Flask `session` in
    production, plain `dict` in unit tests): `login_session` (clears stale
    keys, then sets `user_id` — fixation mitigation), `logout_session`,
    `session_user_id`, `current_user` (session id → live DB row, `None` for
    anonymous or deleted users).
  - Errors derive from a common `AuthError` base.
- **HTTP layer** `social_app/routes.py`: blueprint `auth_bp`, JSON in/out.
  - `POST /auth/register` → 201 `{"id","username"}`; 400 validation; 409 taken;
    415 non-JSON content type; 400 malformed JSON.
  - `POST /auth/login` → 200 `{"id","username"}` + session cookie; 401 bad
    credentials.
  - `POST /auth/logout` → 200 `{"ok": true}`; idempotent when anonymous.
  - `GET /auth/me` → 200 `{"id","username"}` when authenticated, else 401.
  - `login_required` view decorator: 401 JSON `{"error": "authentication
    required"}` for anonymous callers, otherwise injects `user_id=` kwarg.
- **App factory** `social_app/app.py` (minimal FP-002 stand-in): `create_app()`
  runs `db.init_db()` (idempotent), sets `SECRET_KEY` from
  `$SOCIAL_APP_SECRET_KEY` (dev fallback constant), accepts config overrides,
  registers `auth_bp`, and installs a JSON `HTTPException` error handler so
  404/405/415… never return HTML.

## Approach

- Three small modules instead of one: domain logic stays importable and
  testable without a Flask app; routes stay thin (parse → call domain →
  serialize); the factory is the only place that knows about wiring.
- Sessions are Flask's signed cookie sessions — no new table. Login always
  `clear()`s the mapping before writing the new `user_id`, so a stale
  pre-login session (fixation vector) cannot survive and re-login switches
  identity atomically from the caller's viewpoint.
- Route error mapping uses explicit `try/except AuthError` subclasses, keeping
  status codes reviewable at the call site; transport-level errors (bad JSON,
  wrong content type) surface as Flask HTTP exceptions and are normalized to
  JSON by the app-level handler.
- Mock isolation (per task-card header): HTTP tests monkeypatch the domain
  functions on `social_app.routes` to prove the endpoints map errors to status
  codes and never touch the DB themselves; integration tests use a real
  temp DB via `SOCIAL_DB` exactly like the FP-001 suite.

## Key decisions

1. **Same error for unknown user and bad password** — avoids leaking which
   usernames exist; documented as acceptance-level behavior.
2. **`login_required` injects `user_id` kwarg** — the decorator owns the 401
   path once; views never re-check. No current route has a `user_id` URL
   variable, so no collision.
3. **Session helpers take the mapping as a parameter** — no hidden global;
   unit tests pass `dict` and need no request context.
4. **Dev `SECRET_KEY` fallback** — keeps `create_app()` zero-config for local
   runs; production sets `SOCIAL_APP_SECRET_KEY` (tested via env override).
5. **werkzeug default hashing parameters** — scrypt at defaults; no custom
   parameter tuning to audit. `hash_password` is a one-line seam for a future
   policy change.
6. **`create_app` calls `init_db()`** — idempotent per FP-001, so the factory
   doubles as deployment bootstrap; tests point `SOCIAL_DB` at tmp files.

## Verification

`python3 -m pytest tests/test_fp003_auth_session.py -q`, then the full suite
(`python3 -m pytest`). Scenarios in `docs/test-cases/fp003-auth-session.md`.
