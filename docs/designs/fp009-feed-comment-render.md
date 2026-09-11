# FP-009 Design: Feed Comment Render Extensions

Task card: `input/tasks/social-comment-interactions/FP-009-feed-comment-render.task.md`
(sole spec). Goal: extend the feed's comment data so it carries the reply
relation (`parent_id`) and comment-like data (`like_count` / `liked_by_me`), and
render replies nested one level under their parent together with the viewer's
comment-like state.

## Approach

### Query layer (`social_app/feed.py`)

- **`_comments(post_id, viewer_id)` grows a viewer argument** and becomes the
  single source of the new comment contract (card §3.2):
  `comment_id`, `parent_id`, `author`, `content`, `created_at`, `like_count`,
  `liked_by_me`, ordered `created_at ASC, id ASC`.
- **`get_feed` passes `user_id` as the viewer**; its own row shape is unchanged.
- **Capability detection for weak dependencies.** FP-001 (`comment_likes` table)
  and FP-002 (`comments.parent_id`) have not landed, so the query checks
  `PRAGMA table_info(comments)` for `parent_id` and `sqlite_master` for
  `comment_likes`, then composes the SELECT:
  - both present → full contract shape (correlated subqueries for the like
    count and for `EXISTS(... AND user_id = ?)`);
  - `parent_id` absent → `NULL AS parent_id`; `comment_likes` absent → `0` for
    both like fields.
  - **both absent** → the legacy `{author, content, created_at}` shape, so the
    FP-023 exact row assertion keeps passing untouched until the storage tasks
    land (non-regression, card §4/§6).

### Render layer (`social_app/views_feed.py`)

- **Split, don't recurse.** `_split_comments` partitions the list into
  top-level entries (`parent_id is None`) and replies grouped by `parent_id`.
  A reply whose parent is not a known top-level comment (legacy/malformed data)
  is promoted to top-level so it is not dropped; replies are never nested more
  than one level (card §2 "回复（一层）").
- **`_render_comment(entry, replies, *, is_reply)`** renders one escaped `<li>`
  and, for a top-level entry only, appends `_render_replies`; reply entries are
  rendered with `is_reply=True` so no deeper nesting can occur.
- **Sibling helpers stay overridable.** FP-005's `_render_comment_likes` and
  FP-007's `_render_reply_form` / `_render_replies` are the documented contract
  names. Until they land, module-level aliases bind those names to small local
  fallbacks (`_fallback_*`); `_render_comment` calls the names directly, so a
  real sibling definition or a test monkeypatch that rebinds them is used
  immediately, while the module remains independently renderable (card §6).
- **Comment-like fallback.** Because FP-005 has not landed, a missing
  `_render_comment_likes` falls back to a minimal, escaped snippet showing the
  count and the viewer's `已赞` / `未赞` state. This satisfies acceptance 2
  ("展示评论点赞数与该用户已赞态") without owning FP-005's real widget, which
  replaces it as soon as it exists.
- **Escaping** continues to go through `_escaped` for author / content /
  `created_at` (and the fallback's `comment_id` / count), so HTML special
  characters are neutralised.
- **Legacy dicts** (missing `parent_id` / like fields / `comment_id`) default to
  top-level, `0` likes and `False` via the existing `_row_value` accessor.

## Key decisions

1. **Viewer-specific `liked_by_me` from one query.** The correlated
   `EXISTS(... user_id = ?)` keeps `_comments` to a single statement (plus the
   cheap capability probes) and makes the viewer explicit at the call site.
2. **Contract upgrade without breaking FP-023.** Degrading to the legacy shape
   when neither weak-dependency table/column exists avoids editing the existing
   FP-023 exact-equality test, and matches the card §6 "not implemented yet"
   posture.
3. **One-level nesting by construction.** Replies are grouped once; the reply
   renderer never receives children, so a reply cannot spawn a nested list.
4. **Orphan replies are promoted, not lost.** Malformed `parent_id`s cannot
   silently hide a comment from the feed.
5. **No DDL, no routes, no real like widget** (card §5). This module only reads
   and renders.

## Verification

`python3 -m pytest tests/test_fp009_feed_comment_render.py -q`, then the
regression suite `python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp009-feed-comment-render.md`.
