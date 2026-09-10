# FP-014 Design: Feed Page & Empty State

Task card: `FP-014-feed-page.task.md` (sole spec; body embedded in the work
order). Goal: make `GET /` the home feed — render the posts of the users the
current user follows, newest first, show an empty-state guide when there is
nothing to show, and redirect anonymous visitors to `/login`.

## Approach

- **New module `social_app/views_feed.py`** exposing the card §3.3 contract:

  ```python
  def feed_page(request) -> Response   # GET / (home / feed)
  def register(app) -> None            # mounts GET /
  ```

- **Dependencies are imported into the view module's namespace** so tests can
  monkeypatch them (card §6): `require_login` / `current_user_id` from
  `social_app.session` (FP-003) and `get_feed` from `social_app.feed` (FP-005).
  When FP-005 is not landed yet the import falls back to a stub returning `[]`,
  which renders the empty state instead of crashing. Once `social_app/feed.py`
  exists the real query is picked up with no code change.

- **`feed_page` flow** (card §4), in order:

  1. `denied = require_login(request)` — return it unchanged when not `None`
     (303 to `/login`).
  2. `user_id = current_user_id(request)`.
  3. `posts = get_feed(user_id)`.
  4. Non-empty → render one `<article>` per row (username, ISO time, content),
     in the exact order returned. Empty → render the empty-state section
     guiding the user to follow others / publish.

- **Rendering** is stdlib string templates like the rest of FP-001:
  `html_response(title, body)` wraps the fragment. Every data value is passed
  through `html.escape` (content, username, timestamp) so user text can never
  inject markup, and the timestamp is also reused as the `<time datetime>`
  attribute.

- **App wiring**: `social_app/app.py::create_app` mounts the real page via
  `views_feed.register(app)` (imported inside the function to avoid the
  circular import) and the FP-001 `home_page` placeholder is deleted. The
  remaining 501 mount points are untouched.

- **No pagination** (card §5) — the whole `get_feed` result set is rendered.

## Key decisions

1. **View owns orchestration only.** `views_feed` never touches the DB and
   never queries the `follows`/`posts` tables; it calls the FP-005 contract and
   delegates login detection to FP-003, keeping each concern in its own module.
2. **Guard first, then query.** Returning the `require_login` response before
   calling `get_feed` guarantees an anonymous request never reaches the data
   layer and never sees another user's ids (card §7, acceptance 3).
3. **`get_feed` as a module global.** Importing the function with `from ... import`
   (instead of resolving it per call) gives the module a single patch point,
   which is exactly the FP-005/FP-003 isolation the card §6 mock strategy asks
   for.
4. **Empty state is data-driven, not error-driven.** The FP-005 contract
   returns `[]` for "follows nobody" and "followees have no posts", so the same
   empty state covers both; there is no separate "error" branch because the
   contract does not raise for missing data.
5. **Escape everything, including the timestamp.** The card only demands content
   escaping, but username/time are user- or DB-derived too; escaping all three
   removes any injection surface for one extra call each.
6. **Tolerant row accessor.** Real rows are `sqlite3.Row` (key access) while the
   card §6 tests may pass `dict` or `SimpleNamespace`; `_row_value` supports
   subscript and attribute access so the page works with both without a DB.

## Verification

`python3 -m pytest tests/test_fp014_feed_page.py -q`, then the full suite
`python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp014-feed-page.md`.
