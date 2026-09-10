# FP-014 Test Scenarios — Feed Page & Empty State

Module under test: `social_app/views_feed.py` (spec: task card FP-014
§3.3/§4/§7/§8). Dependencies are isolated per card §6: FP-005's `get_feed` is
monkeypatched with dict/`SimpleNamespace` rows; FP-003's login guard is tested
through the real session module for the anonymous case and monkeypatched for
the authenticated cases. Requests are dispatched directly through
`create_app().dispatch(Request(...))` (no live socket), so a 303 can be
inspected instead of followed.

## A. Authenticated feed rendering

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Logged-in user, `get_feed` returns two posts | 200, `text/html`, body contains both contents |
| A2 | `get_feed` order is newest first | Rendered order matches the returned order exactly |
| A3 | Rows carry `username` / `created_at` | Author name and timestamp appear in the page |
| A4 | `get_feed` receives the logged-in id | Called once with `current_user_id(request)` |

## B. Empty state

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Logged-in user, `get_feed` returns `[]` | 200 HTML, empty-state section present |
| B2 | Empty guidance | Page mentions following others and publishing a post |

## C. Login guard

| # | Scenario | Expected |
|---|----------|----------|
| C1 | No session cookie, real `require_login` | 303 with `Location: /login` |
| C2 | Guard returns a redirect | That exact response is returned unchanged |
| C3 | Guard rejects | `get_feed` / `current_user_id` are never called |

## D. Output escaping

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Content contains `<script>alert(1)</script>` | Raw `<script>` absent; escaped form present |
| D2 | Content / username contain `&`, `"`, `'` | Escaped entities rendered, no raw quote injection |
| D3 | Timestamp is escaped too | Raw markup in `created_at` does not produce a tag |

## E. Row shapes & mounting

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Row is a plain `dict` | Renders via key access |
| E2 | Row is a `SimpleNamespace` | Renders via attribute access |
| E3 | `create_app()` route table | `GET /` is registered and maps to `feed_page` |

## F. Integration with the skeleton

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `GET /` anonymous over `create_app` | No longer the 501/placeholder page (redirects) |
| F2 | Other mount points | Remaining 501 placeholders unchanged |

Test file: `tests/test_fp014_feed_page.py`.
