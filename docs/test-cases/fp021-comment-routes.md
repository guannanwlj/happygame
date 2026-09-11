# FP-021 Test Scenarios — Comment Submit Route

Module under test: `social_app/views_comment.py` (`comment_submit`, `register`)
and its mounting in `social_app/app.py::create_app()` (spec: task card FP-021
§4/§7/§8). Tests dispatch the route in-process (`create_app().dispatch` /
direct handler calls), never over the network.

Per card §6 the dependencies are isolated by monkeypatching the module-level
names in `views_comment`: `require_login` / `current_user_id` (FP-003),
`authorize_interaction` (FP-019) and `add_comment` (FP-018). One extra
integration test runs against a fresh temporary DB (`SOCIAL_DB`) with a real
session token to confirm the landed services work end-to-end.

## A. Happy path — logged-in submit saves and redirects home

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Logged-in A, authorizable P, `content=你好`; `add_comment` stub records calls | `303`, `Location == "/"` |
| A2 | Same request | `add_comment` called once with `(P, A, "你好")` |
| A3 | `content=hello+world` | Decoded to `"hello world"` before the service call |
| A4 | Missing `content` field | Service called with `""` (blank left to FP-018) |
| A5 | `authorize_interaction` receives `(actor_id, post_id)` | Called once, before `add_comment` |
| A6 | Integration: real temp DB, A authors P, valid session cookie | Comment row persisted for `(P, A)`; `303 /` |

## B. Blank content — readable error, no write

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `add_comment` raises `CommentError("评论内容不能为空")` | `200`, reason text in body, `<a href="/">` present |
| B2 | Same request | `add_comment` attempted but no comment persisted (stub reports no successful write) |
| B3 | Error message contains HTML (`<b>坏</b>`) | Escaped in the rendered page |

## C. Anonymous — redirect to login, no write

| # | Scenario | Expected |
|---|----------|----------|
| C1 | No session cookie | `303`, `Location == "/login"` |
| C2 | Same request | `add_comment` never called |
| C3 | `require_login` returns a guard response | Returned unchanged (`is` identity), no service call |

## D. Unauthorized — readable error, no write

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `authorize_interaction` raises `InteractionError("无权互动该帖子")` | `200`, reason in body, `<a href="/">` present |
| D2 | Same request | `add_comment` never called |
| D3 | `InteractionError` reason contains HTML | Escaped in the rendered page |

## E. Route mounting / wiring

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `("POST", "/posts/<id>/comments")` in `create_app().routes` | Present |
| E2 | `register` on a bare `SocialApp` | Route present and dispatchable |
| E3 | `GET /posts/1/comments` | `405`, `Allow` lists `POST` |
| E4 | `POST /posts/<id>/comments` reaches the handler (not 404/501) | Handler result (redirect/error), never `501` |

## F. Form / parameter contract

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Path id `1` parsed from `params` | `add_comment` receives post id `1` |
| F2 | Path id `42` | Receives `42` |
| F3 | Extra form fields ignored | Only `content` used |

Skeleton/test file: `tests/test_fp021_comment_routes.py`.
