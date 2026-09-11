# FP-009 Test Scenarios — Feed Comment Render Extensions

Module under test: `social_app/feed.py` (`_comments` / `get_feed` query layer)
and `social_app/views_feed.py` (nested comment rendering) via `GET /`
(spec: task card FP-009 §2–§8).

Isolation (card §6): the query tests seed a fresh temporary database
(`monkeypatch.setenv(db.DB_PATH_ENV, ...)`) and apply the card §3.1
`comments.parent_id` + `comment_likes` DDL, since FP-001/FP-002 have not landed.
The render tests monkeypatch `views_feed.get_feed` with contract-shaped stub rows
(dict / `SimpleNamespace`) and stub FP-003's guard; no database is touched.

Seed data (card §6): users `alice` and `bob`; post `p1` by `alice`; top-level
comment `c1` (`parent_id NULL`) and reply `c2` (`parent_id=c1`); one comment like
`(bob, c1)`.

## A. Acceptance 1/4 — query contract and reply relation

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `_comments(p1, viewer)` on the §3.1 schema | Each dict has `comment_id`, `parent_id`, `author`, `content`, `created_at`, `like_count`, `liked_by_me` |
| A2 | `c1` top-level / `c2` reply | `c1["parent_id"] is None`; `c2["parent_id"] == c1["comment_id"]` |
| A3 | `get_feed(alice)` comments | Same upgraded shape via the feed row (not only the private helper) |
| A4 | Multiple replies, same parent | Ordered `created_at ASC, id ASC` |

## B. Acceptance 2 — comment like data and viewer state

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `(bob, c1)` like stored | `c1["like_count"] == 1` |
| B2 | Viewer is `bob` | `c1["liked_by_me"] is True` |
| B3 | Viewer is `alice` | `c1["liked_by_me"] is False`, count still `1` |
| B4 | Render as the liker | Body shows the comment count and the `已赞` state |

## C. Acceptance 1/3/5 — rendering

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Comment with a reply | `<ul class="reply-list">` nested inside the parent `<li class="comment">`; reply content after parent content |
| C2 | Reply entry | Rendered `class="comment reply"`; exactly one `reply-list` (no deeper nesting) |
| C3 | Comment content `<script>alert(1)</script>` | Raw tag absent; `&lt;script&gt;alert(1)&lt;/script&gt;` present |
| C4 | Comment author/time special chars | Raw tags absent; escaped forms present |
| C5 | Legacy dict (author/content/created_at only) | 200, rendered as top-level, no error, no `reply-list` |
| C6 | No `parent_id`/like keys | Default top-level, `0` likes, `未赞` state |

## D. Integration hooks (card §3.2 / §6)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `_render_comment_likes` monkeypatched in | Its fragment is used instead of the fallback |
| D2 | `_render_reply_form` monkeypatched in | Its form is used on top-level comments |
| D3 | `_render_replies` monkeypatched in | Its reply block is used instead of the local list |
| D4 | Sibling helpers absent | Module still renders (empty form, local reply list, fallback likes) |

## E. Non-regression (card §4)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Legacy DB schema (no `parent_id`, no `comment_likes`) | `_comments` returns the legacy `{author, content, created_at}` shape; FP-023 suite passes unchanged |
| E2 | FP-014/FP-022 row stubs | Feed page still renders likes/comments/empty state |

Skeleton/test file: `tests/test_fp009_feed_comment_render.py`.
