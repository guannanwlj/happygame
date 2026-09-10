# FP-003 Design: Session / Login State (Social Platform)

Task card: `input/tasks/social-platform-mvp/FP-003-session.task.md`
(sole spec, embedded in the work order). Goal: an in-process token→user
session store (`social_app/session.py`) that establishes / validates /
invalidates sessions and gives the web layer a `require_login` guard for
protected pages.

## Approach

- One new module `social_app/session.py`; no existing runtime code touched.
- In-process mapping `token -> user_id` guarded by `threading.Lock`, so a
  `ThreadingHTTPServer` can serve concurrent requests safely. Nothing is
  persisted: a process restart drops every session (card §2).
- Public contract (card §3.3):

  ```python
  SESSION_COOKIE = "session"

  create_session(user_id: int) -> str        # secrets.token_urlsafe(32)
  get_user_id(token: str | None) -> int | None
  destroy_session(token: str | None) -> None # idempotent
  current_user_id(request) -> int | None     # reads request.cookies
  require_login(request) -> Response | None  # None = allowed, else 303 /login
  cookie_header(token: str) -> str
  clear_cookie_header() -> str
  ```

- `require_login` builds its redirect through `social_app.app.redirect`
  (FP-001, card §3.2). Because FP-001 for `social_app` is not implemented
  yet (only `social_app/db.py` exists), the lookup is **lazy per call** and
  falls back to a minimal local `Response`-shaped object when the import
  fails. This is the card §6 Mock strategy and keeps `session.py`'s public
  signatures unchanged; once FP-001 lands, the same call site uses the real
  redirect automatically.

## Key decisions

1. **Lazy app import with fallback** — a module-level `redirect` name points
   at a resolver that tries `from social_app.app import redirect` at call
   time and uses an inline fallback otherwise. Consequences:
   - the module imports and the guard works before FP-001 exists;
   - monkeypatching `social_app.session.redirect` swaps the redirect
     behaviour (tests assert the 303/`Location: /login` contract without a
     web framework);
   - no top-level import of a module that does not exist yet (no
     `ImportError` at collection time).
2. **Lock around every access** — `create_session`, `get_user_id` and
   `destroy_session` take the lock even for reads. Dict operations are
   atomic under CPython, but the lock makes the safety guarantee explicit
   and portable, and keeps the door open for multi-statement session
   bookkeeping later.
3. **Missing / invalid token is uniformly "not logged in"** — `get_user_id`
   returns `None` for `None`, `""`, or an unknown token; `destroy_session`
   silently no-ops on the same inputs (idempotence, card §7). Callers never
   need to distinguish "no cookie" from "stale cookie".
4. **Defensive cookie access** — `current_user_id` uses
   `getattr(request, "cookies", None)` so a request object without a
   `cookies` attribute is treated as anonymous instead of raising. The real
   `Request` (FP-001) always carries the field; the fallback keeps unit
   tests (card §6 `SimpleNamespace` stand-in) honest.
5. **Cookie header strings are exact literals** — `cookie_header` returns
   `session=<token>; HttpOnly; Path=/`; `clear_cookie_header` returns
   `session=; HttpOnly; Path=/; Max-Age=0`. No `Secure` flag: the MVP runs
   over plain HTTP on localhost. The lock is not held while formatting.
6. **`secrets` for token generation** — `token_urlsafe(32)` yields a
   ~256-bit unguessable token, matching the card's explicit requirement and
   avoiding the `random` module for security-relevant values.

## Verification

`python3 -m pytest tests/test_fp003_session.py -q` (plus the full suite).
Scenarios documented in `docs/test-cases/fp003-session.md`.
