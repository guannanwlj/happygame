# FP-020 Design: Like / Unlike HTTP Routes

Task card: `FP-020-like-routes.task.md` (sole spec). Goal: add
`social_app/views_like.py` exposing `POST /posts/<id>/like` and
`POST /posts/<id>/unlike`, and mount them in
`social_app/app.py::create_app()`. The module orchestrates
「登录保护 → 归属校验 → 点赞服务 → 303 回首页」and never touches the
database itself.

## Approach

- **One new view module `social_app/views_like.py`**, mirroring the
  guard → service → feedback shape of `social_app/views_follow.py`.
- **Dependencies imported as module-level names** (card §4) so tests and
  callers can monkeypatch them:
  `from social_app.like_service import like, unlike` and
  `from social_app.interaction_service import InteractionError,
  authorize_interaction`. The session helpers
  (`require_login`, `current_user_id`) and the FP-001 web helpers
  (`html_response`, `redirect`) are imported the same way.
- **Public contract (card §3.2):**

  ```python
  def like_submit(request) -> Response     # POST /posts/<id>/like
  def unlike_submit(request) -> Response   # POST /posts/<id>/unlike
  def register(app) -> None
  ```

- **Shared flow.** `like_submit` / `unlike_submit` delegate to one private
  `_submit(request, operation)` so the two routes cannot drift:

  1. `require_login(request)`; a non-`None` response (the 303 to `/login`) is
     returned directly.
  2. `post_id = int(request.params["id"])` — the router fills `params`.
  3. `authorize_interaction(current_user_id(request), post_id)`.
  4. `operation(actor_id, post_id)` (`like` or `unlike`); the return count is
     unused here — FP-022 renders totals.
  5. `return redirect("/")` → 303 See Other.

- **Error handling.** `InteractionError` (raised by step 3) is caught and
  rendered as a 200 HTML page with `html.escape(str(exc))` and
  `<a href="/">返回首页</a>`, following the `views_follow.py` failure-page
  convention. No like/unlike call happens on that path, so a denied request
  performs no write.
- **Mounting.** `register(app)` registers both POST routes. `create_app()`
  imports and calls `views_like.register(app)` alongside the existing
  `views_follow.register` / `views_post.register` calls. The import stays
  inside `create_app()` (not at module top) to avoid the circular import
  between `app.py` and the view modules.

## Key decisions

1. **Order is exactly card §4: login → parse id → authorize → service.**
   Anonymous callers are short-circuited by `require_login` before any
   service call, satisfying "no write when anonymous" structurally.
2. **One `_submit` helper for both verbs.** Like and unlike differ only by the
   service function, so a single flow removes duplication; the operation is
   passed as a callable resolved at call time, keeping `views_like.like` /
   `views_like.unlike` monkeypatchable.
3. **No redirect on error.** Authorization failures render a readable page
   (status 200) instead of redirecting, matching the follow-UI precedent and
   the acceptance wording "返回可读错误页".
4. **Success redirects to `/` with 303**, i.e. `redirect("/")` and not
   `redirect("/", 302)`, so the browser re-issues a GET for the feed.
5. **No database access, no rendering of like state.** Storage lives in
   FP-015/FP-017 and post-stream rendering in FP-022; this module only
   orchestrates HTTP.
6. **`int(request.params["id"])` per the card.** Malformed ids are not given a
   special page — the router/card contract assumes a numeric segment.

## Verification

`python3 -m pytest tests/test_fp020_like_routes.py -q`, then the full suite.
Scenarios documented in `docs/test-cases/fp020-like-routes.md`.
