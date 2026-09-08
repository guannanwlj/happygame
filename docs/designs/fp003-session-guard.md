# FP-003 Design: Session Management & Protected-Page Access Control

Task card: FP-003 (sole spec, embedded in the task dispatch). Goal: deliver
`social_app/guard.py` — the single source of the session contract
(login/logout/current id + `login_required`) that FP-005..FP-013 will consume,
built on Flask's signed-cookie `session`.

## Approach

- One new module `social_app/guard.py`, Flask-only (no DB access): login state
  lives entirely in `session["user_id"]` per card §3.1 — no per-request user
  lookups here, so the guard stays a pure session primitive.
- Four public functions, exactly as the contract slice in §3.2:
  - `login_user(user_id)` → `session["user_id"] = user_id` (assignment
    overwrites, so a new login invalidates the old one by construction);
  - `logout_user()` → `session.clear()` (full session destruction, not just
    key removal — the card wording is explicit);
  - `current_user_id()` → `session.get("user_id")` (`None` when signed out);
  - `login_required(view)` decorator → if `current_user_id()` is `None`,
    `redirect("/login")` using the **literal path** (never `url_for`, to avoid
    a compile-time dependency on the FP-006 login-page endpoint); otherwise
    call the view unchanged. `functools.wraps` keeps view metadata (endpoint
    naming, debugging, docstrings).
- Nothing else: no login/logout views, no registration hook, no business
  pages (§5 — those are FP-005/FP-006/FP-007+).

## Key decisions

1. **Literal `"/login"` redirect, 302**: `flask.redirect` defaults to 302,
   matching the acceptance wording; the literal string decouples this module
   from whether the login endpoint exists yet.
2. **No DB in the guard**: §3.1 says login-state checks only read the session;
   users-table reads stay with callers that need the username.
3. **Demo blueprint lives only in tests** (§4/§6): FP-001's `create_app` is
   not merged yet, so the test suite builds a minimal `Flask(__name__)` app
   with `secret_key` set and mounts a `/demo-protected` route behind
   `login_required`, plus `/demo-login/<uid>` / `/demo-logout` /
   `/demo-whoami` routes that exercise the primitives over HTTP. When
   `social_app.app.create_app` lands, the fixture prefers it and still
   registers the demo blueprint — same assertions either way.
4. **Seed data via `social_app.db`** (§6): tests insert the card's seed row
   (`id=1, username="alice", password_hash="h"`, plus a second user for the
   overwrite scenario) through the FP-001 API with `SOCIAL_DB` pointing at a
   tmp file, then drive login state with `session_transaction` — realistic
   without coupling the guard to the DB.

## Verification

`python3 -m pytest tests/test_fp003_session_guard.py -q` (plus the full
suite). Scenarios documented in `docs/test-cases/fp003-session-guard.md`.
