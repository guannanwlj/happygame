# FP-022 Test Scenarios — Feed Render Extensions

Module under test: `social_app/views_feed.py` rendering (`_render_post`) via
`GET /` (spec: task card FP-022 §2–§8). FP-023's `get_feed` is monkeypatched with
contract-shaped row stubs (dict / `SimpleNamespace`), matching the existing
FP-014 isolation; FP-003's guard is stubbed so a logged-in user id 7 is used. No
database is touched.

Seed data (card §6): post P1 has `like_count=3`, `liked_by_me=True`, post_id 1,
and two comments at ascending times (`alice` older, `carol` newer) whose content
includes HTML special characters; post P2 has `comments=[]`, `like_count=0`,
`liked_by_me=False`.

## A. Acceptance 1 — like total and like/unlike entry

| # | Scenario | Expected |
|---|----------|----------|
| A1 | P1 liked by the viewer, `like_count=3` | `<span class="like-count">3</span>` present |
| A2 | P1 `liked_by_me=True` | Form `action="/posts/1/unlike"`, button 「取消点赞」 |
| A3 | P1 `liked_by_me=True` | No `action="/posts/1/like"` form |
| A4 | P2 `liked_by_me=False` | Form `action="/posts/1/like"`, button 「点赞」 |
| A5 | P2 `liked_by_me=False` | No `/unlike` form; count `0` rendered |

## B. Acceptance 3 — comment list, ascending

| # | Scenario | Expected |
|---|----------|----------|
| B1 | P1 has two comments (ascending) | Older content appears before newer content in the body |
| B2 | P1 comments | Each renders `author`, `created_at` (text + `datetime`) and `content` |
| B3 | Comment form | `action="/posts/1/comments"`, `<textarea name="content">`, submit button |
| B4 | Comments rendered as a list | `<ul class="comment-list">` with one `<li class="comment">` per comment |

## C. Acceptance 4 — empty state keeps input

| # | Scenario | Expected |
|---|----------|----------|
| C1 | P2 `comments=[]` | `<p class="comments-empty">暂无评论</p>` present |
| C2 | P2 `comments=[]` | Comment form still rendered (`/posts/1/comments`, textarea) |
| C3 | P2 `comments` key absent | Same empty state, still renders (default `[]`) |

## D. Acceptance 5 — escaping

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Comment content `<script>alert(1)</script>` | Raw tag absent; `&lt;script&gt;` present |
| D2 | Comment author `<b>eve</b>` / time `<i>t</i>` | Raw tags absent; escaped forms present |
| D3 | Post content/username/time special chars | Escaped (FP-014 suite continues to pass) |

## E. Non-regression (card §4)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | FP-014 row stub only (`username/content/created_at`) | `GET /` is 200, post still renders |
| E2 | FP-014 row stub | Default like entry (`/like`, count `0`) and empty comments shown |
| E3 | `SimpleNamespace` contract row | Same interaction rendering as a dict row |

## F. Guard / contract

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Anonymous visitor | 303 to `/login`, no feed query (FP-014 suite continues to pass) |
| F2 | `get_feed` call order | Guard first, then `get_feed(current_user_id(request))` |

Skeleton/test file: `tests/test_fp022_feed_interactions.py`.
