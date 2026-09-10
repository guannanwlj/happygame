# FP-008 Test Scenarios — Login Page and Logout (Social Platform)

Module under test: `social_app/views_login.py` (spec: task card FP-008 §3.3 /
§4 / §6 / §7 / §8). Requests are dispatched directly through the real FP-001
`create_app()` registry (`app.dispatch(Request(...))`); authentication
(FP-009) and session invalidation (FP-003) are monkeypatched, per card §6.

Seed data (card §6): form body `b"username=alice&password=secret1"`;
`cookies={"session": "tok-1"}` for a logged-in logout; mocked success token
`"tok-1"`, mocked failure `None`.

## A. Acceptance — card §7

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Guest `GET /login` | `200` HTML with `name="username"` and `name="password"` inputs |
| A2 | `POST /login`, auth returns `"tok-1"` | `303`, `Location == "/"`, `Set-Cookie: session=tok-1; HttpOnly; Path=/` |
| A3 | `POST /login`, auth returns `None` | `200` page containing `认证失败`, no `Location` header |
| A4 | `POST /logout` with `session` cookie | `destroy_session("tok-1")` called, expired `session` cookie, `303` → `/login` |

## B. Login page rendering (`login_page`)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `GET /login` body | HTML page with `<title>`/heading `登录` |
| B2 | Form action/method | `action="/login"` + `method="post"` |
| B3 | Logout entry | page contains a `POST /logout` form (`action="/logout"`) |
| B4 | `GET /login` is not the old placeholder | status is `200`, not `501` |

## C. Login submit (`login_submit`)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Success | token forwarded to `Set-Cookie`; redirect 303; auth called with parsed username/password |
| C2 | Failure | 200, `认证失败`, no redirect |
| C3 | Empty body / missing fields | auth called with `("", "")`, treated as failure |
| C4 | Username with `<script>` on failure | echoed escaped (`&lt;script&gt;`), raw `<script>` absent |
| C5 | Auth is called exactly once with the submitted credentials | one call, `("alice", "secret1")` |

## D. Logout (`logout`)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Logged-in request | `destroy_session` receives the exact cookie token |
| D2 | Redirect | `303`, `Location == "/login"` |
| D3 | Cookie clearing | `Set-Cookie` equals `session=; HttpOnly; Path=/; Max-Age=0` |
| D4 | Anonymous request (no cookie) | `destroy_session(None)` still called; cookie still cleared; 303 |

## E. Route mounting (`register` / `create_app`)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `register(app)` on a fresh app | installs exactly `GET /login`, `POST /login`, `POST /logout` |
| E2 | `create_app()` routes | the three login/logout routes are present |
| E3 | Re-register over skeleton | dispatching `GET /login` runs the real handler (no 501) |

## F. Cookie contract

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Success cookie | equals `social_app.session.cookie_header(token)` |
| F2 | Logout cookie | equals `social_app.session.clear_cookie_header()` |

Test file: `tests/test_fp008_login_page.py`.
