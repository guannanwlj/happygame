# FP-005 Design: 用户登录与登出 (Login & Logout)

Task card: `input/tasks/social-platform/FP-005-login-logout.task.md` (sole spec).

## Goal

Deliver the login page (`GET/POST /login`) and the logout entry (`POST /logout`)
as a Flask blueprint `social_app/login.py` + `templates/login.html`.
Correct credentials establish a session (login state); wrong credentials show
a single unified error 「用户名或密码错误」 and establish **no** session.

## Dependency situation (card §3/§6)

| Dependency | Status at coding time | Strategy |
|---|---|---|
| FP-001 storage | merged | use `social_app/db.py` (`init_db`, `query_one`, `execute`) as-is |
| FP-003 auth/session | not merged | create `social_app/auth.py` matching the card §3.2 contract exactly (`hash_password`, `verify_password`, `login_user`, `logout_user`, `current_user_id`, `login_required`) with an **inline stdlib PBKDF2** implementation (integration point I-07 swaps the real one in) |
| FP-002 web skeleton | not merged | create a minimal app factory `social_app/app.py` (`create_app()`) that mounts the blueprint + a `/` index route; FP-002's real factory replaces it |
| FP-004 registration | not merged (weak) | tests seed the user by direct `INSERT` (card §6): `alice` with `hash_password("alice-pass-123")` |

## Approach

1. `social_app/auth.py` — session helpers on top of `flask.session`; password
   hashing with `hashlib.pbkdf2_hmac("sha256", ...)` (60k iterations, 16-byte
   random salt). Stored format `pbkdf2_sha256$<iterations>$<salt-hex>$<digest-hex>`
   so iteration count travels with the hash. `verify_password` parses the stored
   string and returns `False` (never raises) on any malformed value, comparing
   digests with `hmac.compare_digest`. `login_required` redirects anonymous
   users to `url_for("login.login", next=request.path)` → `302 /login?next=<path>`.
2. `social_app/login.py` — `bp = Blueprint("login", __name__)` (template folder
   defaults to `social_app/templates/`):
   - `POST /login`: look the user up by exact username via
     `db.query_one("SELECT id, password_hash FROM users WHERE username = ?")`;
     if found and `verify_password` passes → `login_user(id)` and 302 to the
     `next` target when it is a **safe relative path** (starts with `/`, not
     `//`, no backslash — blocks open-redirect), else to `/`. Any failure
     (unknown username, wrong password, missing/empty fields, malformed stored
     hash) renders `login.html` with the unified error — no branch differences,
     no user-enumeration signal.
   - `GET /login`: render the form (a hidden `next` field carries the query
     parameter through the POST).
   - `POST /logout`: `logout_user()` then 302 to `/login` (safe even when no
     session exists).
3. `social_app/app.py` — minimal factory: sets `SECRET_KEY` (env
   `SOCIAL_SECRET_KEY`, dev default), runs idempotent `db.init_db()`, registers
   the login blueprint, exposes `/`.
4. Templates — `base.html` (title/content blocks) and `login.html` extending it
   (username + password fields, error slot). Self-built shell per card §6.

## Key decisions

1. **Unified error message, single code path**: unknown user and wrong password
   render the same message with the same status 200 — the card explicitly
   forbids distinguishing them, and it doubles as anti-enumeration.
2. **Fail-closed `verify_password`**: any parse error → `False`, so a corrupted
   `password_hash` row degrades to "wrong credentials" instead of a 500.
3. **`next` safety rule** (`/`-prefixed, not `//`-prefixed, no `\`) applied
   before redirecting; anything else falls back to `/`. Tested against
   absolute-URL and protocol-relative payloads.
4. **Session via cookie jar**: production code only touches `flask.session`
   through the auth contract; tests use Flask's test client (cookies persist
   across requests) plus `session_transaction()` to assert session state.
5. **No registration here**: seed users are inserted directly (card §6); the
   full register→login loop is booked as FP-004 integration item I-08.
6. **CI untouched**: workflow deps are FP-012's scope.

## Verification

`python3 -m pytest tests/test_fp005_login.py -q`, then the full suite
(`python3 -m pytest -q`). Scenarios in `docs/test-cases/fp005-login-logout.md`.
