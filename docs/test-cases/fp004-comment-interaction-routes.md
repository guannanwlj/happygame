# FP-004 Test Scenarios — Comment Interaction Submit Routes

Module under test: `social_app/views_comment_interaction.py`
(`comment_like_submit`, `comment_unlike_submit`, `comment_reply_submit`,
`register`) and its mounting in `social_app/app.py::create_app()` (spec: task
card FP-004 §4/§7/§8). Tests dispatch the routes in-process
(`create_app().dispatch` / direct handler calls), never over the network and
never following redirects.

Per card §6 the dependencies are isolated by monkeypatching the module-level
names in `views_comment_interaction`: `require_login` / `current_user_id`
(FP-003 session), `authorize_comment_interaction` (FP-003), `like_comment` /
`unlike_comment` (FP-006) and `add_reply` (FP-008). Seed: `actor_id=7`,
comment id `1`, form `content="hi"`.

## A. Happy path — logged-in, authorized like

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Logged-in actor, authorizable comment, `like_comment` stub succeeds | `303`, `Location == "/"` |
| A2 | Same request | `like_comment` called once with `(7, 1)` |
| A3 | Same request | `unlike_comment` never called |
| A4 | `authorize_comment_interaction` receives `(actor_id, comment_id)` | Called once with `(7, 1)`, before the service |

## B. Happy path — logged-in, authorized unlike

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Logged-in actor, authorizable comment, `unlike_comment` stub succeeds | `303`, `Location == "/"` |
| B2 | Same request | `unlike_comment` called once with `(7, 1)`; `like_comment` never called |

## C. Happy path — logged-in, authorized reply

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Logged-in actor, authorizable parent, `content=hi` | `303`, `Location == "/"` |
| C2 | Same request | `add_reply` called once with `(parent_id, actor_id, content) == (1, 7, "hi")` |
| C3 | `content=hello+world` | Decoded to `"hello world"` before the service call |
| C4 | Missing `content` field | Service called with `""` (blank left to FP-008) |

## D. Anonymous — redirect to login, no service call

| # | Scenario | Expected |
|---|----------|----------|
| D1 | No session cookie, `POST /comments/1/like` | `303`, `Location == "/login"`; no service/authorize call |
| D2 | No session cookie, `POST /comments/1/unlike` | `303`, `Location == "/login"`; no service/authorize call |
| D3 | No session cookie, `POST /comments/1/replies` | `303`, `Location == "/login"`; no service/authorize call |

## E. Authorization denied — readable error, no write

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `authorize_comment_interaction` raises `InteractionError("评论不存在")` | `200`, reason in body, `<a href="/">返回首页</a>` present |
| E2 | Same request for like / unlike / reply | Service never called, no successful write |
| E3 | Denial reason contains HTML (`<b>坏</b>`) | Escaped in the rendered page |

## F. Service rejection — readable error, no write

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `add_reply` raises `ReplyError("回复内容不能为空")` | `200`, reason in body, `<a href="/">` present |
| F2 | Same request | No redirect (`Location` absent) and no successful write |
| F3 | `ReplyError` reason contains HTML | Escaped in the rendered page |

## G. Route mounting / wiring

| # | Scenario | Expected |
|---|----------|----------|
| G1 | `("POST", "/comments/<id>/like")` in `create_app().routes` | Present |
| G2 | `("POST", "/comments/<id>/unlike")` in `create_app().routes` | Present |
| G3 | `("POST", "/comments/<id>/replies")` in `create_app().routes` | Present |
| G4 | `register` on a bare `SocialApp` | All three routes present |
| G5 | `GET` on any of the three paths | `405`, `Allow` lists `POST` |
| G6 | `POST` reaches the mounted handler (not 404/501) | Handler result, never `501` |

## H. Parameter contract

| # | Scenario | Expected |
|---|----------|----------|
| H1 | Path id `42` for like | `like_comment` receives comment id `42` |
| H2 | Path id `42` for reply | `add_reply` receives parent id `42` |

Skeleton/test file: `tests/test_fp004_comment_interaction_routes.py`.
