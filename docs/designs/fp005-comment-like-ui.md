# FP-005 Design: Comment Like / Unlike Entry and Liked State

Task card: `FP-005-comment-like-ui.task.md` (sole spec). Goal: render, next to
every comment in the home feed, the comment's like total plus a like / unlike
POST form that reflects the current viewer's state and points at the FP-004
comment interaction routes.

## Approach

### Where the code lives

- **One new public helper in `social_app/views_feed.py`**:
  `_render_comment_likes(entry) -> str`. The module already calls this name from
  `_render_comment` (FP-009), so replacing the placeholder alias with the real
  function wires it into every rendered comment — top-level and reply alike —
  without touching the comment/reply orchestration.
- **`_fallback_comment_likes` and its module-level alias are removed.** FP-009
  introduced the fallback only because FP-005 had not landed; the real function
  now fulfils the documented contract name. The FP-007 reply fallbacks stay.
- The helper is a pure renderer: no database access, no routes, no counting
  / idempotency / authorization logic (card §5). It consumes the FP-009 row
  contract (`comment_id`, `like_count`, `liked_by_me`) provided by
  `get_feed`.

### Output shape

Per the card §4 example, plus a `comment-liked-state` text span:

```html
<div class="comment-likes">
  <span class="comment-like-count">3</span>
  <span class="comment-liked-state">已赞</span>
  <form class="comment-like-form" action="/comments/1/unlike" method="post">
    <button type="submit">取消点赞</button>
  </form>
</div>
```

- Unliked: `action="/comments/<id>/like"`, button 「点赞」, state 「未赞」.
- Liked: `action="/comments/<id>/unlike"`, button 「取消点赞」, state 「已赞」.
- The state span keeps the FP-009 acceptance (B4/C6) that the viewer's liked
  state is displayed, while the button label carries the FP-005 action wording.
  It contains no `/like"` / `/unlike` substring, so the FP-005 negative
  assertions are unaffected.

### Defaults and escaping

- `like_count` defaults to `0` and `liked_by_me` to `False` through the existing
  `_row_value` accessor, so legacy comment dicts / `sqlite3.Row` /
  `SimpleNamespace` rows without the FP-009 keys still render (card §4).
- Every interpolated value goes through `_escaped` (`comment_id`, `like_count`),
  which applies `html.escape` to the stringified value. The `liked_by_me` bool
  is coerced with `bool(...)` and only selects among fixed literals, so it can
  never inject markup.

## Key decisions

1. **Reuse the FP-009 call site.** `_render_comment` already invokes
   `_render_comment_likes`; the task is a drop-in real implementation, not a new
   integration path.
2. **Keep the viewer-state text alongside the button.** FP-005 owns the
   like/unlike entry point, but FP-009's render tests assert the `已赞` / `未赞`
   state; emitting both keeps the whole suite green and gives users an explicit
   state label.
3. **Fixed label/action pairs, never interpolated user text.** The only dynamic
   parts of the action URL and label are the escaped `comment_id` and the
   boolean branch.
4. **No fallback retained.** Unlike FP-007 (still unlanded), FP-005's real
   implementation now exists, so the local fallback would only be dead code.

## Verification

`python3 -m pytest tests/test_fp005_comment_like_ui.py -q`, then the regression
suite `python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp005-comment-like-ui.md`.
