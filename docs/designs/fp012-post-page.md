# FP-012 Design: Post Page (Social Platform)

Task card: `FP-012-post-page.task.md` (sole spec; body embedded in the work
order). Goal: render the post form and orchestrate submission — a logged-in
user posts plain text, the FP-013 core validates and writes, and the UI shows
either a redirect on success or a 200 page with the error message and the
form preserved.

## Approach

- One new module `social_app/views_post.py` plus a small wiring change in
  `social_app/app.py` (`create_app` mounts the two real handlers over the
  FP-012 placeholders).
- Public contract (card §3.3):

  ```python
  def post_form(request) -> Response     # GET  /posts/new
  def post_submit(request) -> Response   # POST /posts
  def register(app) -> None              # app.route the two paths
  ```

- Handlers:

  1. `post_form`: `require_login(request)`; if it returns a response, return
     it unchanged (303 to `/login`). Otherwise render the form page
     (`<textarea name="content">`).
  2. `post_submit`: `require_login`; otherwise `parse_form(request.body)` →
     `content` (missing field = `""`), resolve `author_id` via
     `current_user_id(request)`, call `posts.create_post(author_id, content)`.
     - success → `redirect("/")` (303; POST → GET, card §4);
     - `posts.PostError` (empty / anonymous) → `html_response(..., status=200)`
       with `html.escape(str(exc))` rendered as the error and the submitted
       text echoed back (also escaped).

- `register(app)` calls `app.route("GET", "/posts/new", post_form)` and
  `app.route("POST", "/posts", post_submit)`, replacing the FP-001
  placeholders through the registry's replace-on-duplicate semantics.

## Key decisions

1. **Lazy access to the FP-013 module.** `views_post` never imports
   `social_app.posts` at module import time; a small `_load_posts()` helper
   resolves `from social_app import posts` per call. This mirrors FP-003's
   lazy `redirect` resolver and keeps the card §6 mock strategy available:
   tests monkeypatch `social_app.posts.create_post` (and the module may be
   absent while FP-013 is still a scheduling dependency). It also avoids a
   hard import failure taking down the whole `create_app()` skeleton if
   FP-013 has not landed.
2. **Module-level `require_login` / `current_user_id` names.** They are
   imported from `social_app.session` at module level so the card §6 mocks
   (`monkeypatch.setattr(views_post, "require_login", ...)`) work, and so the
   guard is called through a patchable seam.
3. **Redirect on success, not a success page.** Card §4/§7 accept either;
   303 to `/` keeps the POST/redirect/GET pattern and hands the feed off to
   FP-014. Tests assert `status == 303` and `Location == "/"`.
4. **Errors are 200, never a redirect.** `/posts` re-renders the form so the
   user can fix the text; the submitted value is echoed with `html.escape`.
5. **`content` defaults to `""`.** A body without the field still routes
   through `create_post`, which reports `内容不能为空` — the handler itself
   does not re-implement validation (card §5).
6. **No direct DB / storage access in the view.** All persistence belongs to
   FP-013; this module only calls the contract.
7. **`register(app)` is why `create_app` does not hardcode the handlers.**
   `create_app()` does a local `from social_app import views_post` inside the
   function to avoid a circular import (`views_post` imports
   `social_app.app`).

## Verification

`python3 -m pytest tests/test_fp012_post_page.py -q` (plus the full suite).
Scenarios documented in `docs/test-cases/fp012-post-page.md`.
