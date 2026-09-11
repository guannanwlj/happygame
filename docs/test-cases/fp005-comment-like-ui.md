# FP-005 Test Scenarios — Comment Like / Unlike Entry and Liked State

Module under test: `social_app/views_feed.py::_render_comment_likes` via the
home feed `GET /` (spec: task card FP-005 §4 / §7).

Isolation (card §6): the render tests monkeypatch `views_feed.get_feed` with
contract-shaped stub rows (dict / `SimpleNamespace`), and stub FP-003's
`require_login` / `current_user_id`, so no database and no FP-001 / FP-003 /
FP-004 / FP-009 runtime output are required. The helper itself is also called
directly for the escaping and defaulting cases.

Seed data (card §6): unliked comment
`{"comment_id":1,"parent_id":None,"author":"alice","content":"hi","created_at":"2026-01-01T00:00:00Z","like_count":0,"liked_by_me":False}`;
liked comment with `comment_id=2`, `like_count=3`, `liked_by_me=True`.

## A. Acceptance — unliked comment

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `like_count=0`, `liked_by_me=False` rendered | `<span class="comment-like-count">0</span>` present |
| A2 | Same row | `class="comment-like-form" action="/comments/1/like"` present |
| A3 | Same row | Button text 「点赞」 present; `/unlike` absent |
| A4 | Same row | State `未赞` present (FP-009 B4/C6) |

## B. Acceptance — liked comment

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `like_count=3`, `liked_by_me=True` rendered | `<span class="comment-like-count">3</span>` present |
| B2 | Same row | `action="/comments/2/unlike"` present |
| B3 | Same row | Button text 「取消点赞」 present; `/like"` absent |
| B4 | Same row | State `已赞` present (FP-009 B4/C6) |

## C. Acceptance — defaults and escaping

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Comment row missing `like_count` / `liked_by_me` | Count `0`, action `.../like`, 「点赞」, `未赞`, page 200 |
| C2 | Comment author/content contain HTML special chars | Raw tags absent; escaped text present |
| C3 | `comment_id` contains HTML special chars | Action value escaped; no raw markup injected |
| C4 | `sqlite3.Row` / `SimpleNamespace` row shape | Renders via `_row_value` (no `KeyError` / `TypeError`) |

## D. Integration / non-regression

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Every comment in a post (top-level and reply) | Each carries its own `.comment-likes` fragment |
| D2 | `_render_comment_likes` monkeypatched | Monkeypatched fragment used instead (FP-009 D1 still passes) |
| D3 | FP-009 suite unchanged | `已赞` / `未赞` state assertions still pass |

Skeleton/test file: `tests/test_fp005_comment_like_ui.py`.
