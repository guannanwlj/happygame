# FP-005 Design: Post Form Image Selection (Social Platform)

Task card: `input/tasks/post-image-upload/FP-005-post-form-images.task.md`
(sole spec; body embedded in the work order). Goal: the post form
(`social_app/views_post.py`) gains a native multi-file picker and switches to
multipart encoding, while the existing error/content refill mechanism stays
untouched. Pure view-layer change — no schema, no handler logic.

## Approach

- Single edit to the `_FORM_TEMPLATE` string in `social_app/views_post.py`:

  1. `<form method="post" action="{action}">` gains
     `enctype="multipart/form-data"` so browsers submit multipart bodies.
  2. After the existing `<textarea>` block, add the card §4 file picker
     verbatim:

     ```html
     <label for="images">图片</label>
     <input type="file" id="images" name="images" multiple
            accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp">
     ```

- Nothing else changes: `post_form` / `post_submit` / `_form_html` /
  `register` keep their FP-012 contracts (card §3.2). `_form_html`'s
  `str.format` placeholders remain `{action}` / `{content}` only; the new
  markup introduces no braces.

## Key decisions

1. **Field names are the FP-006 contract.** Text stays `name="content"`;
   files are `name="images"` with `multiple` (card §3.2 convention). FP-006's
   submit integration will parse the multipart part named `images`.
2. **`accept` lists extensions *and* MIME types** exactly as the card §4
   snippet prescribes (`.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp`)
   — duplicates are intentional for cross-browser coverage and kept verbatim
   so the contract is greppable.
3. **`post_submit` is deliberately untouched** (card §5). Between this task
   and FP-006 landing, a real browser multipart POST is not yet decodable
   server-side; the two tasks merge in the same window. Tests therefore
   exercise the rejection path with a urlencoded body, which the current
   `parse_form` already decodes.
4. **No client-side pre-validation / preview** (card §5: upstream D-5 defers
   previews; validation concentrates in the service layer FP-002 via FP-006).
5. **Login state is real, not stubbed, in tests** (card §6): a seeded
   `users` row in a temp `SOCIAL_DB` plus `session.create_session(uid)`
   provide the token, mirroring `tests/test_fp014_feed_page.py`. The
   rejection scenario monkeypatches `social_app.posts.create_post` to raise
   `PostError("图片数量不能超过 9 张")` and rides the existing re-render
   channel.
6. **Refill mechanism unchanged.** `_form_html(content, error)` still escapes
   both; the textarea echo and `<p class="error">` banner behave exactly as
   FP-012 tested.

## Verification

`python3 -m pytest tests/test_fp005_post_form_images.py -q` (plus the full
suite). Scenarios documented in `docs/test-cases/fp005-post-form-images.md`.
