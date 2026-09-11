# FP-022 Design: Feed Render Extensions

Task card: `input/tasks/social-like-comment/FP-022-feed-render.task.md` (sole
spec). Goal: extend the existing home feed (`social_app/views_feed.py`) so each
post also renders its like total, the viewer's like state, a like/unlike form, a
comment form, and the comment list — all HTML-escaped. This closes the visible
side of UC-001…UC-004.

## Approach

- **Render-only change to `social_app/views_feed.py`.** `feed_page`'s guard and
  fetch order (`require_login` → `current_user_id` → `get_feed`) are untouched;
  only `_render_post` grows, by delegating to two new helpers.
- **Consume the FP-023 row contract** (card §3.2): `post_id`, `like_count`,
  `liked_by_me`, `comments` (`[{author, content, created_at}]`, ascending).
  No DB access here.
- **Three small render helpers** keep `_render_post` readable:
  - `_render_likes(row)` — `<span class="like-count">N</span>` plus a form whose
    action is `/posts/<post_id>/unlike` (label 「取消点赞」) when
    `liked_by_me` is truthy, otherwise `/posts/<post_id>/like` (label 「点赞」).
  - `_render_comments(row)` — the `action="/posts/<post_id>/comments"` form with
    `<textarea name="content">` + submit button, followed by the comment list
    (author, time, content in the order given) or the empty state
    `<p class="comments-empty">暂无评论</p>`.
  - `_render_comment(comment)` — one `<li>` for a comment.
- **`_row_value(row, key, default=None)`** gains a default. The FP-014 rows are
  plain `{username, content, created_at}`; asking for the new keys now yields
  `""` / `0` / `False` / `[]` instead of raising, so the older test stub still
  renders (non-regression, card §4). It stays tolerant of `sqlite3.Row`, `dict`
  and `SimpleNamespace` (card §6).
- **Escaping** goes through one `_escaped(row, key, default)` wrapper
  (`html.escape(str(_row_value(...)))`), used for username, time, content and
  every comment field — including the `post_id` interpolated into form actions.

## Key decisions

1. **Defaults live in `_row_value`, not in callers.** Missing keys are a
   first-class "old row / not provided" case, so the four documented defaults
   are applied at the accessor and every caller benefits.
2. **`liked_by_me` keeps its boolean type.** `_row_value` returns the raw value
   (no `str()`), so `False` is not coerced into the truthy string `"False"`.
   String coercion happens only in `_escaped` for text nodes/attributes.
3. **Empty comment state is data-driven.** `comments` empty/`None` selects the
   empty-state paragraph; the comment form is rendered either way, preserving
   the input entry point (card §2).
4. **Form routes are hard-coded strings** (`like` / `unlike` / `comments`).
   FP-020/FP-021 own the handlers; this task only points the forms at the paths
   agreed in card §3.2.
5. **No pagination, no replies/edit/delete** (card §5), and no change to the
   `GET /` route or login guard.

## Verification

`python3 -m pytest tests/test_fp022_feed_interactions.py tests/test_fp014_feed_page.py -q`,
then the full suite `python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp022-feed-render.md`.
