# FP-003 Design: Authentication & Session Management

Task card: `input/tasks/social-platform/FP-003-auth-session.task.md` (FP-003,
P0, M1, wave 2). The card was originally absent from this checkout; a canonical
copy was recovered and committed at that path, and it is now the **sole
implementation basis**. An earlier attempt on this branch had self-built a
different contract (scrypt hashing, JSON-401 `login_required`,
register/login/logout/me endpoints, an app factory). That attempt is replaced:
this changeset rewrites `social_app/auth.py` to the card's §3.2 contract and
deletes the out-of-scope modules (`routes.py`, `app.py`), per card §5.

## Goal (card §1)

Deliver password hashing & verification, login-session establish / maintain /
destroy, and the `login_required` gate for protected features — i.e. module
`social_app/auth.py` — as the single reusable enforcement point for the
platform's "credentials are username+password, plaintext never at rest"
constraint (D-004).

## Contract implemented (card §3.2, verbatim API)

```python
def hash_password(plain: str) -> str        # PBKDF2-HMAC-SHA256 + random salt,
    # self-contained format "pbkdf2:sha256$<iterations>$<salt_hex>$<hash_hex>"
def verify_password(plain: str, stored: str) -> bool
    # recompute per stored format, constant-time compare; bad format -> False
def login_user(user_id: int) -> None        # session['user_id'] = user_id
def logout_user() -> None                   # session.clear()
def current_user_id() -> int | None         # session.get('user_id')
def login_required(view)                    # anonymous -> 302 /login?next=<path>
```

## Dependency posture (card header rule + §6)

- **FP-001 (merged)**: use the real `social_app.db` (via `SOCIAL_DB`) and its
  `users` table; no embedded DDL stand-in needed. DB-backed tests point
  `SOCIAL_DB` at `tmp_path` exactly like the FP-001 suite.
- **FP-002 (not merged)**: no repo-level `create_app` is created. Per card §6,
  each test builds a minimal `Flask(__name__)` shell with a `secret_key`,
  registers a `@login_required`-protected dummy route, and verifies the gate
  through the Flask test client. Login/logout are driven by tiny test-only
  routes that call the real `login_user`/`logout_user`.

## Approach

- `social_app/auth.py` is the only production module (card §4). Hashing uses
  `hashlib.pbkdf2_hmac` directly (no werkzeug dependency), producing exactly
  the card's self-contained format.
- Session helpers wrap Flask's signed-cookie `session` directly — no mapping
  indirection; they require a request context, which tests provide via the
  minimal shell.
- `login_required` preserves the wrapped view's metadata (`functools.wraps`)
  and redirects anonymous callers with `next` set to the URL-quoted request
  path so the (future, FP-005) login page can return the user afterwards.

## Key decisions

1. **PBKDF2 parameters**: SHA-256, 16-byte salt from `secrets.token_hex(16)`,
   600 000 iterations — werkzeug's default for `pbkdf2:sha256`, satisfying the
   card's "语义等价" clause without importing werkzeug; format separators are
   the card's `$` layout, not werkzeug's colon layout.
2. **`verify_password` is strict and safe on hostile input**: parse failure
   (wrong arity, non-hex, non-numeric or non-positive iteration count,
   non-string) returns `False`; iteration counts above 1 000 000 are rejected
   before any KDF work (CPU-abuse guard); comparison via
   `hmac.compare_digest` (constant time).
3. **`login_user` only sets the key** (card literally specifies
   `session['user_id'] = user_id`) — it does not clear unrelated keys; the
   card gives session destruction solely to `logout_user`.
4. **`login_required` returns 302 to `/login?next=<request.path>`**, per card
   §3.2/§7. JSON/401 semantics belong to API-style tasks, not this card.
5. **Scope is trimmed to §4/§5**: no registration/login pages or flows
   (FP-004/FP-005), no protected business routes, no users-table maintenance
   (FP-001). The earlier stand-ins for those live in git history if needed.
6. **Seed data per card §6**: `alice` with `hash_password("alice-pass-123")`
   in a temp DB; used by the acceptance flow, which checks credentials by
   `verify_password` against the stored row without building FP-005 screens.

## Verification

Card §8: `python3 -m pytest tests/test_fp003_auth.py -q`, then the full suite
`python3 -m pytest`. Scenarios: `docs/test-cases/fp003-auth-session.md`.
