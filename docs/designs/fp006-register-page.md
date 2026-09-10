# FP-006 Design: Register Page (Social Platform)

Task card: `input/tasks/social-platform-mvp/FP-006-register-page.task.md`
(sole spec). Goal: the visitor-facing registration page in a new module
`social_app/views_register.py`. It renders the username/password form, hands
submissions to the FP-007 registration core, logs the new account in on
success, and re-renders the form with a reason on failure.

## Approach

- One new module `social_app/views_register.py` and a mount call added to
  `create_app()` in `social_app/app.py`. No storage code: account validation
  and creation stay in FP-007 (`social_app/accounts.py`).

- Public contract (card §3.3):

  ```python
  def register_page(request) -> Response     # GET /register
  def register_submit(request) -> Response   # POST /register
  def register(app) -> None                  # mount both on app
  ```

- `register_page` returns `html_response("注册", <form>)` (200). The form
  posts urlencoded `username` and `password` fields back to `/register` and
  offers a submit button.

- `register_submit` uses `parse_form(request.body)` to read the fields, then
  calls `accounts.register(username, password)`:
  - success `(user_id, token)` → `redirect("/")` (303) with
    `Set-Cookie: session=<token>; HttpOnly; Path=/` built by
    `social_app.session.cookie_header`;
  - `RegisterError` → re-render the form with the readable reason at 200
    (no redirect), preserving the typed username.

- All user-controlled text echoed into the page is passed through
  `html.escape(..., quote=True)` so `username` cannot break out of the value
  attribute or inject markup (card §4 / §7).

- `register(app)` calls `app.route("GET", "/register", register_page)` and
  `app.route("POST", "/register", register_submit)`. `create_app()` invokes
  it so the two former `not_implemented(... "FP-006")` placeholders become
  the real handlers (the router's re-registration semantics replace them).

## Key decisions

1. **Lazy `accounts` import** — `views_register` resolves
   `from social_app import accounts` inside `register_submit` rather than at
   module import time. Per card §6 the module must import and be testable
   even when FP-007 is not mounted yet; the lazy lookup lets a test substitute
   `social_app.accounts` and keeps the dependency edge at the single call
   site. Once FP-007 lands, the same call site uses the real module.
2. **Exception class resolved from the same module** — `RegisterError` is
   caught as `accounts.RegisterError`, so a substituted module defines the
   error type it raises; no import of FP-007 at module scope is required.
3. **Mount inside `create_app` via a lazy import** — `app.py` imports
   `views_register` inside `create_app()` to avoid a module-level import
   cycle (`views_register` imports `Request`/`Response`/helpers from
   `app.py`). Routing is still declarative: removing the two placeholder
   lines and mounting the real handlers is the whole change.
4. **`session.cookie_header` as the single cookie source** — the
   `Set-Cookie` string is not re-spelled here; FP-003 already owns the
   `session=<token>; HttpOnly; Path=/` contract (card §3.2), so flags cannot
   drift between login and registration.
5. **Escape on echo, not on render** — `html_response` already escapes the
   page title; the body is intentionally raw HTML. Every interpolated
   username/reason is escaped at interpolation, keeping the template readable
   while closing the reflected-XSS path.
6. **No validation duplication** — the view does not trim, length-check, or
   dedupe; it forwards the raw fields and renders whatever `RegisterError`
   message FP-007 produced. Empty/None fields become `""` so FP-007 owns the
   "用户名不能为空" message.

## Verification

`python3 -m pytest tests/test_fp006_register_page.py -q` (then the full suite).
Scenarios documented in `docs/test-cases/fp006-register-page.md`.
