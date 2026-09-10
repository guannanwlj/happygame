# FP-003 Test Scenarios — Session / Login State (Social Platform)

Module under test: `social_app/session.py` (spec: task card FP-003 §3.3 /
§6 / §7 / §8). Pure in-process state, no database, no real web framework.
Requests are the card §6 `SimpleNamespace(cookies=...)` stand-ins; the
`redirect` path is monkeypatched on `social_app.session` so the 303 /
`Location` contract is asserted directly.

Seed data (card §6): arbitrary user ids `1`, `2`, `7`; tokens produced by
`create_session`; an anonymous request (no/empty/unknown `session` cookie).

## A. Acceptance — card §7

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `create_session(7)` then `get_user_id(token)` | `7` |
| A2 | request with `cookies={"session": token}` → `current_user_id` | `7` |
| A3 | request with no / empty / invalid token → `require_login` | `303`, `Location == "/login"` |
| A4 | logged-in request → `require_login` | `None` |
| A5 | `destroy_session(token)` then `get_user_id(token)`; call again | `None`; second call does not raise |
| A6 | `cookie_header(token)` / `clear_cookie_header()` | contain `session=<token>`, `HttpOnly`, `Path=/` / `Max-Age=0` |

## B. Establishment & lookup

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Two `create_session` calls | distinct tokens (also across many calls) |
| B2 | Tokens are `token_urlsafe(32)`-shaped | URL-safe, length ≥ 32, no `;`/space/`=` |
| B3 | Different users' sessions looked up independently | each `get_user_id` returns its own id |
| B4 | `get_user_id(None)` / `get_user_id("")` / `get_user_id("nope")` | `None` |
| B5 | Storing user id `0` | returned as `0`, not confused with missing |

## C. Invalidation

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `destroy_session("nope")` (never created) | no raise |
| C2 | `destroy_session(None)` / `destroy_session("")` | no raise |
| C3 | Destroy one of two sessions | the other remains valid |
| C4 | Destroy then recreate a fresh session | new token is valid, old is gone |

## D. Request integration (`current_user_id`)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Request object with `cookies` attribute | resolves user id |
| D2 | Request without `cookies` attribute | `None` (defensive, no raise) |
| D3 | `cookies={}` / `cookies={"session": "bogus"}` | `None` |
| D4 | Other cookies present alongside `session` | ignores the rest |
| D5 | `SESSION_COOKIE` constant is `"session"` | matches contract |

## E. `require_login`

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Anonymous request | `redirect("/login")` called once; returned status `303` |
| E2 | Returned headers | `Location == "/login"` |
| E3 | Logged-in request | `None` and `redirect` never called |
| E4 | Expired/destroyed session cookie | treated as anonymous → 303 |
| E5 | Monkeypatched `session.redirect` receives the login path | `/login` |

## F. Cookie header helpers

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `cookie_header("abc")` | `"session=abc; HttpOnly; Path=/"` |
| F2 | `clear_cookie_header()` | `"session=; HttpOnly; Path=/; Max-Age=0"` |
| F3 | Header round-trips: `cookie_header` value is not session state | no side effects on store |

## G. Thread safety smoke (ThreadingHTTPServer context)

| # | Scenario | Expected |
|---|----------|----------|
| G1 | 8 threads each `create_session(i)` | all tokens distinct and resolvable to `i` |
| G2 | Concurrent `destroy_session` on the same token | no raise, token gone |

Test file: `tests/test_fp003_session.py`.
