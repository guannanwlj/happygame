# FP-003 Test Scenarios — Comment Interaction Authorization

Module under test: `social_app/interaction_service.py`
(`COMMENT_NOT_FOUND_MESSAGE`, `authorize_comment_interaction`) against the
existing `users` / `posts` / `follows` / `comments` tables (spec: task card
FP-003 §3/§4/§7/§8). Every test uses a fresh temporary DB file via the
`SOCIAL_DB` env var, calls `db.init_db()`, then seeds users/posts/follows/
comments — no shared state, no repo pollution.

Seed helpers used throughout: `insert_user(username)`, `insert_post(author)`,
`add_comment(post, author)`, `follow(follower, followee)`, `table_counts()`
(row count of every table in `sqlite_master`) and `schema_snapshot()`
(`sqlite_master` SQL text, so no DDL change survives a denial).

Canonical seed (card §6): users `author`, `follower`, `stranger`;
post `p1(author)`; comment `c1(post=p1, author=author)`;
follow `follower → author`.

## A. Anonymous actor denied

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `c1` exists; `authorize_comment_interaction(None, c1)` | Raises `InteractionError("未登录")` |
| A2 | Row counts + `sqlite_master` before vs. after A1 | Unchanged |
| A3 | Anonymous actor on an existing comment does not touch `comments`/`posts`/`follows` | Unchanged |

## B. Stranger denied (logged in, neither author nor follower)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `stranger` is logged in, is not the post author and does not follow `author`; call on `c1` | Raises `InteractionError` |
| B2 | Error text of B1 | Readable Chinese `"无权互动该帖子"` |
| B3 | Row counts + `sqlite_master` before vs. after B1 | Unchanged |

## C. Post author allowed

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `author` of `p1` (and of `c1`) calls on `c1` | Returns `None` |
| C2 | Comment author differs from post author, but actor is the post author | Returns `None` (post口径 governs) |
| C3 | Row counts before vs. after C1 | Unchanged |

## D. Follower of the post author allowed

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `follower` follows `author`; call on `c1` | Returns `None` |
| D2 | Row counts before vs. after D1 | Unchanged |
| D3 | Directionality: comment author follows actor does not authorize | Denied |

## E. Missing comment denied

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Logged-in actor, `comment_id = 9999` | Raises `InteractionError` |
| E2 | Error text of E1 | Readable Chinese `"评论不存在"` |
| E3 | Anonymous actor, `comment_id = 9999` | `"评论不存在"` wins over the login check (card order) |
| E4 | Comment deleted after id was known | Raises `InteractionError("评论不存在")` |
| E5 | Row counts + `sqlite_master` before vs. after E1 | Unchanged |

## F. Contract / hook points

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `issubclass(InteractionError, Exception)` | `True` |
| F2 | `COMMENT_NOT_FOUND_MESSAGE` value | `"评论不存在"` |
| F3 | `authorize_comment_interaction` return on allow | Exactly `None` |
| F4 | Monkeypatch `interaction_service.authorize_interaction` → raises for a given actor | Denial propagates as `InteractionError` |
| F5 | Module has no write path during deny: monkeypatch `db.execute` to raise | Denial still raises `InteractionError`, never `AssertionError` |

Skeleton/test file: `tests/test_fp003_comment_authorization.py`.
