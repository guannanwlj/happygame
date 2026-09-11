# FP-020 Test Scenarios — Like / Unlike HTTP Routes

Module under test: `social_app/views_like.py` (`like_submit`, `unlike_submit`,
`register`) dispatched through a real `create_app()` (spec: task card FP-020
§4/§7/§8). Per card §6 the FP-017 service and FP-019 guard are monkeypatched
in the `views_like` namespace, and the FP-003 session helpers
(`require_login` / `current_user_id`) are stubbed so no DB/session setup is
needed. The "no write" scenarios assert the like/unlike service is never
called.

Constants: `ACTOR_ID = 42`, `POST_ID = "7"`, `LIKE_PATH`,
`UNLIKE_PATH`.

## A. Logged-in like (acceptance 1)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Logged-in A, authorized P, `POST /posts/7/like` | Status 303, `Location == "/"` |
| A2 | Same request | `like` called once with `(42, 7)` |
| A3 | Same request | Not an error page: no `错误`/failure banner in body |
| A4 | `unlike` service | Not called by the like route |

## B. Logged-in unlike (acceptance 2)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Logged-in A, authorized P, `POST /posts/7/unlike` | Status 303, `Location == "/"` |
| B2 | Same request | `unlike` called once with `(42, 7)` |
| B3 | `like` service | Not called by the unlike route |

## C. Anonymous (acceptance 3)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | No session, `POST .../like` | Status 303, `Location == "/login"` |
| C2 | Same request | `like` and `authorize_interaction` never called (no write) |
| C3 | No session, `POST .../unlike` | Status 303, `Location == "/login"`; `unlike` never called |

## D. Unauthorized (acceptance 4)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `authorize_interaction` raises `InteractionError("无权互动该帖子")` | Status 200, readable Chinese reason in body |
| D2 | Same request | `<a href="/">返回首页</a>` present |
| D3 | Same request | `like` never called (no write) |
| D4 | Denied reasons are escaped; `InteractionError("<b>坏</b>")` | Raw markup absent, `&lt;b&gt;坏&lt;/b&gt;` present |
| D5 | `unlike` path with a guard error | Also renders the readable page and never calls `unlike` |

## E. Route mounting / contract

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `create_app()` routes | `("POST", "/posts/<id>/like")` and `("POST", "/posts/<id>/unlike")` present |
| E2 | `views_like.register` on a bare `SocialApp` | Both routes registered |
| E3 | `GET` on either path | 405 with `POST` in `Allow` |
| E4 | `id` from the path reaches the service | Nested pattern value (`/posts/7/...` → `7`) is what gets passed |
| E5 | Public contract | `like_submit` / `unlike_submit` / `register` are callable |

Skeleton/test file: `tests/test_fp020_like_routes.py`.
