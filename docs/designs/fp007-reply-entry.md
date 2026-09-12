# FP-007 Design: Reply Entry Point

Task card: `input/tasks/social-comment-interactions/FP-007-reply-entry.task.md`
(sole spec). Goal: under every top-level comment render a reply input + submit
entry pointing at FP-004's `POST /comments/<id>/replies`, and nest that
comment's replies directly beneath it in ascending time order.

## Approach

This is a pure render task (card §4/§5): `social_app/views_feed.py` owns the
reply widgets, consumes the FP-009 comment contract (`parent_id`) and never
touches the database or the submit route.

### Real helpers replace the FP-009 fallbacks

FP-009 left `_render_reply_form` / `_render_replies` bound to local
`_fallback_*` stubs so the module stayed independently renderable. FP-007 lands
the real implementations and drops the reply fallbacks:

- **`_render_reply_form(entry)`** — an escaped
  `<form class="reply-form" action="/comments/<comment_id>/replies"
  method="post">` with `<textarea name="content">` and a `回复` submit button.
  The action comes from the entry's `comment_id`, read through `_row_value`
  (dict / `sqlite3.Row` / `SimpleNamespace`).
- **`_render_replies(entry, replies)`** — a `<ul class="reply-list">` whose
  items are `_render_comment(reply, is_reply=True)`. Order is the caller's;
  `_split_comments` already delivers siblings `created_at ASC, id ASC`
  (FP-009), so the renderer preserves insertion order and adds no sort.
- **`_render_comment(entry, replies, *, is_reply=False)`** keeps composing
  them: form + nested list are appended only for entries presented as
  top-level (`is_reply=False`). Replies are rendered with `is_reply=True`, so
  the one-level rule holds by construction and a reply never grows its own
  reply entry point (card §4).

`_render_comment_likes` stays bound to `_fallback_comment_likes` — that widget
belongs to FP-005 and is out of scope here.

### Escaping

Every reply field (`author`, `created_at`, `content`) continues to flow through
the existing `_escaped` helper, and the form's `comment_id` through
`_escaped`/`_row_value`, so HTML special characters in data or in an id cannot
break out of the markup.

### Mock/verification posture (card §6)

No dependency on FP-002/FP-004/FP-009 at runtime: tests monkeypatch
`views_feed.require_login`, `views_feed.current_user_id` and
`views_feed.get_feed` with contract-shaped stub rows and dispatch
`GET /` through `create_app()`, so the rendering is verified in isolation.

## Key decisions

1. **Render-only ownership.** No route, DDL, validation or authorization is
   added (card §5); the form only points at FP-004's route.
2. **Ordering delegated to the data layer.** `_render_replies` does not sort;
   the FP-009 contract already promises ascending order and re-sorting here
   would duplicate that rule.
3. **One-level nesting by construction.** `_render_replies` always recurses
   with `is_reply=True`, so nesting cannot deepen even if data is malformed.
4. **Real names, not aliases.** Defining `_render_reply_form` / `_render_replies`
   directly keeps FP-009's monkeypatch-override test passing (the names remain
   module globals) while giving the contract its real implementation.

## Verification

`python3 -m pytest tests/test_fp007_reply_entry.py -q`, then the regression
suite `python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp007-reply-entry.md`.
