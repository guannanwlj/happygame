# FP-006 Test Scenarios — Register Page (Social Platform)

Module under test: `social_app/views_register.py` (spec: task card FP-006
§3.3 / §4 / §7 / §8). Handlers are driven directly through
`SocialApp.dispatch(Request(...))` — no socket required. FP-007
(`social_app.accounts`) is substituted per card §6 by installing a stub
module as `social_app.accounts` (or monkeypatching the real module's
`register` when it exists), so success returns `(1, "tok")` and failure
raises `RegisterError("用户名已被占用")`.

Seed data (card §6): valid body `b"username=alice&password=secret1"`, short
secret body `b"username=alice&password=123"`, an HTML `username` containing
`<script>`.

## A. Acceptance — card §7

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `GET /register` | 200, `Content-Type` html, page contains `name="username"`, `name="password"`, a submit button |
| A2 | Valid `POST /register` (mock returns `(1, "tok")`) | 303, `Location == "/"`, `Set-Cookie == "session=tok; HttpOnly; Path=/"` |
| A3 | `POST /register` where mock raises `RegisterError("用户名已被占用")` | 200, page shows the reason, no `Location` header |
| A4 | `POST /register` with `username=<script>alert(1)</script>` and mock raising | body escapes to `&lt;script&gt;`, contains no raw `<script>` |

## B. Form parsing and delegation

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `b"username=alice&password=secret1"` | `accounts.register` called once with `("alice", "secret1")` |
| B2 | Percent/plus encoded body (`a+b`, `p%40ss`) | register receives the decoded `"a b"` / `"p@ss"` |
| B3 | Empty body | register called with `("", "")` (FP-007 owns the message) |
| B4 | Extra/unrelated fields | ignored; only username/password forwarded |

## C. Cookie contract (FP-003)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Successful submit | `Set-Cookie` equals `session.cookie_header(token)` |
| C2 | Successful submit | cookie contains `session=`, `HttpOnly`, `Path=/` |
| C3 | Failed submit | no `Set-Cookie` header emitted |

## D. Routing / mounting

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `register(app)` | `GET /register` → `register_page`, `POST /register` → `register_submit` |
| D2 | `create_app()` then dispatch the routes | real handlers run (not the 501 placeholder) |
| D3 | `register(app)` twice | idempotent; routes still resolve to the handlers |
| D4 | `create_app()` route table | both `("GET", "/register")` and `("POST", "/register")` present |

## E. Rendering / escaping

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `register_page` | 200, HTML doctype, form `action="/register"` `method="post"` |
| E2 | Error re-render echoes back the typed username | escaped username appears inside the value attribute |
| E3 | Error message echoed | HTML-escaped (no raw markup) |
| E4 | `register_page` does not touch `accounts` | no import/registration call on GET |

Test file: `tests/test_fp006_register_page.py`.
