# FP-003 Design: Friend-Post Comment Visibility Filter (feed convergence point)

Task card: `input/tasks/comment-visibility-mutual-friends/FP-003-comment-visibility-filter.task.md`
(sole spec). Goal: at the feed's single comment-read convergence point, dispatch
per post — own posts and non-mutual posts keep showing every comment (status
quo), mutual-friend posts only show comments/replies authored inside the
visible set `mutual_friend_ids(R, P) ∪ {P} ∪ {R}`, and any failure while
deciding yields an empty list (fail-closed, prefer showing less).

## Approach

- **New pure dispatch module.** `social_app/comment_visibility.py` exposes
  exactly one function with the card §3.2 signature (frozen for FP-004):
  `visible_comments(post_author_id, viewer_id, comments) -> list`. It first
  dispatches on the relationship: `viewer == post_author` or
  `not is_mutual_follow(post_author, viewer)` returns `comments` **unchanged**
  (same list object, same order); otherwise each row (top-level or reply,
  judged independently) is kept iff its `author_id` is in
  `mutual_friend_ids(viewer, post_author) ∪ {post_author_id, viewer_id}`.
  Rows are accessed by key so both `sqlite3.Row` and `dict` work.
- **Fail-closed.** The entire judgment (dispatch + set computation + row
  access) runs inside one `try/except Exception`: any error returns `[]`, so a
  post can never leak an unconfirmed-visible comment. Downstream, an empty
  comment list renders the existing `<p class="comments-empty">暂无评论</p>`.
- **Real dependencies, no fallbacks.** FP-001 (`is_mutual_follow`) and FP-002
  (`mutual_friend_ids`) already merged in wave 1, so per card §6 (wave-2
  recommendation) both are imported directly — no try/except inline
  substitutes. Real-time fallback after an unfollow comes for free: both
  primitives derive from the live `follows` table, so the dispatch check turns
  false and the post reverts to showing everything.
- **Convergence-point wiring.** `feed._comments(post_id, viewer_id,
  post_author_id=None)` now selects `c.author_id` in every SQL branch, filters
  the raw rows through `visible_comments` *before* assembling the contract
  dicts, and keeps the FP-009 dict shape (`comment_id`, `parent_id`,
  `author`, `content`, `created_at`, `like_count`, `liked_by_me`) and the
  `created_at ASC, id ASC` order untouched — filtering is a pure subset
  selection, never a re-sort. `get_feed` passes each post row's `author_id`
  explicitly (no extra query). When `post_author_id` is omitted (legacy
  two-argument callers from FP-009 tests), it is resolved with one
  `SELECT author_id FROM posts WHERE id = ?` so those callers still get full
  filtering semantics; signature changes stay inside the feed module (card
  §3.2).
- **Rendering untouched.** Hidden parents leave their visible replies
  parentless in the list; the existing `views_feed._split_comments`
  parent-missing promotion then lifts those replies to top level — the card's
  required combination, with zero rendering changes. `require_login`
  (303 → `/login`) is not touched.

## Key decisions

1. **Filter raw SQL rows, not assembled dicts**: `author_id` rides along the
   existing queries and is dropped again when building the FP-009 dicts, so
   the consumed contract stays byte-for-byte identical for FP-009/FP-014/
   FP-022/FP-023.
2. **Identity return for the unfiltered branch** ("原样返回"): the same list
   object is returned, making the no-filter path trivially observable for
   FP-004's matrix.
3. **One broad `except Exception` around the whole judgment**: the card names
   relationship-data anomalies as the example; row-shape errors are covered
   the same way ("宁可少显示").
4. **Dispatch before set computation**: the mutual-friend set query runs only
   for actual friend posts, keeping own-post/non-mutual posts at status-quo
   cost (no extra reads).
5. **Optional `post_author_id` with DB fallback** instead of a hard signature
   break: keeps `feed._comments(post, viewer)` callers (FP-009 regression
   tests) working while `get_feed` always supplies the id it already holds.
6. **No writes, no schema changes, no route changes**: read-only visibility
   layering; write paths, forms and pagination stay out (card §5).

## Verification

`python3 -m pytest -q tests/test_comment_visibility.py
tests/test_feed_visibility.py` (the 11 card §7 GWT items), feed regressions
`python3 -m pytest -q tests/test_fp009_feed_comment_render.py
tests/test_fp014_feed_page.py tests/test_fp022_feed_interactions.py
tests/test_fp023_feed_query.py`, then the full `python3 -m pytest -q`.
Scenarios documented in `docs/test-cases/fp003-comment-visibility.md`.
