# FP-010 Test Scenarios — Follow Operation UI

Module under test: `social_app/views_follow.py` plus the `POST /follow` mount in
`social_app/app.py` (spec: task card FP-010 §3.3/§4/§7/§8). Tests dispatch
`Request("POST", "/follow", body=b"target_username=...")` through a real
`create_app()` and isolate the dependencies per card §6:

- FP-011: `social_app.follow_service.follow` is monkeypatched (returns `None`,
  records its args, or raises `FollowError`).
- FP-003: `social_app.views_follow.require_login` is monkeypatched to return
  `None` (logged in) or a 303 response (anonymous), and
  `social_app.views_follow.current_user_id` supplies the actor id.

## A. Happy path — successful follow

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Logged-in actor submits existing target `bob` | `200`; page contains `关注成功` and `返回首页` link (`href="/"`) |
| A2 | Same request, service patched to record args | `follow(actor_id, "bob")` called exactly once with resolved actor id |
| A3 | Repeated follow (service idempotent, returns `None`) | Same `200` success page; no error text |

## B. Anonymous request

| # | Scenario | Expected |
|---|----------|----------|
| B1 | No session; `require_login` returns 303 → `/login` | Response is that 303 redirect; `Location: /login` |
| B2 | Anonymous request | `follow_service.follow` is never called (no write attempt) |

## C. Rule violations rendered as feedback

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Service raises `FollowError("用户不存在")` | `200`; page contains `用户不存在`; not a redirect |
| C2 | Service raises `FollowError("不能关注自己")` | `200`; page contains `不能关注自己` |
| C3 | Service raises `FollowError("未登录")` (race after guard) | `200`; page contains `未登录` |

## D. Input handling

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Body `b"target_username=bob"` | Service receives `"bob"` |
| D2 | Missing `target_username` field | Service receives `""` (blank, still rendered) |
| D3 | Blank field `target_username=` | Service receives `""` |
| D4 | Extra form fields present | Only `target_username` is consumed |

## E. HTML escaping

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Success with target `<script>alert(1)</script>` | Raw `<script>` absent; `&lt;script&gt;` present |
| E2 | `FollowError` message containing HTML | Message escaped in the error page |
| E3 | Target with `&` / quotes | `&amp;` / `&#x27;` present, raw payload absent |

## F. Route mounting / registry

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `create_app()` registry | Contains `("POST", "/follow")` |
| F2 | `POST /follow` through `create_app()` | No longer the FP-010 501 placeholder |
| F3 | `register(app)` on a bare `SocialApp` | Mounts `follow_submit` for `POST /follow` |
| F4 | `GET /follow` | `405 Method Not Allowed` with `Allow: POST` |

Skeleton/test file: `tests/test_fp010_follow_ui.py`.
