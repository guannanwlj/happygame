# FP-008 Design: Login Page and Logout (Social Platform)

Task card: `input/tasks/social-platform-mvp/FP-008-login-page.task.md`
(sole spec, embedded in the work order). Goal: a new module
`social_app/views_login.py` that renders the login form, orchestrates
authentication through FP-009, and exposes the logout entry. The three routes
`GET /login`, `POST /login`, `POST /logout` are mounted over the FP-001 501
placeholders in `create_app()`.

## Approach

- One new module `social_app/views_login.py`; the only existing runtime file
  touched is `social_app/app.py` (mount the real handlers in `create_app()`).
- Public contract (card §3.3):

  ```python
  def login_page(request) -> Response      # GET /login
  def login_submit(request) -> Response    # POST /login
  def logout(request) -> Response          # POST /logout
  def register(app) -> None                # mount all three routes
  ```

- `login_page` renders the form fragment (`name="username"`,
  `name="password"`, a `POST /logout` entry) through FP-001
  `html_response`.
- `login_submit` runs `parse_form(request.body)` → FP-009
  `login(username, password)`:
  - success → `redirect("/")` with `Set-Cookie: <session.cookie_header(token)>`;
  - failure (`None`) → re-render the login page with the uniform
    `认证失败` message, HTTP 200 and no redirect.
- `logout` reads `request.cookies["session"]`, calls
  `destroy_session(token)`, then redirects to `/login` with the expired
  cookie header (`clear_cookie_header()`). A missing cookie degrades to
  `destroy_session(None)` (a no-op) but still clears the cookie.
- `register(app)` registers the three handlers through the FP-001
  re-register-replaces registry, so mounting in `create_app()` simply drops
  the 501 placeholders.

## Key decisions

1. **Lazy FP-009 seam** — the module exposes a thin
   `login(username, password)` wrapper that resolves
   `social_app.auth.login` at call time (with a fail-closed `None` fallback
   when the module is absent). This mirrors the lazy-import pattern used by
   `social_app.session` (FP-003 design) and is the card §6 mock strategy:
   tests monkeypatch `social_app.views_login.login`, and once FP-009 lands
   the same call site uses the real authenticator unchanged.
2. **Direct imports for the FP-003 helpers** — `destroy_session`,
   `cookie_header`, `clear_cookie_header` and `SESSION_COOKIE` are imported
   into the module namespace so the card §6 `monkeypatch
   social_app.views_login.destroy_session` assertion works and the Cookie
   literals stay owned by FP-003.
3. **Uniform failure message** — a `None` token (unknown user *or* wrong
   password) always renders the same `认证失败` text and a 200 status; no
   redirect, no distinction, so the page cannot be used to enumerate
   accounts (card §1/§2, acceptance §7-3).
4. **Echoed username is escaped** — on failure the submitted username is
   re-filled into the form but passed through `html.escape`, so a crafted
   `username=<script>` cannot inject markup.
5. **Logout is POST-only** — `GET /logout` is not registered; a state change
   must not be triggerable by a top-level navigation. The expired
   `Set-Cookie` is always sent, even for an anonymous request, so a stale
   cookie is cleared.
6. **No DB access / no session storage here** — credential checking stays in
   FP-009 and token storage in FP-003; this module only renders and
   orchestrates, per card §5.

## Verification

`python3 -m pytest tests/test_fp008_login_page.py -q` (plus the full suite).
Scenarios documented in `docs/test-cases/fp008-login-page.md`.
