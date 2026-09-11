# FP-021 Design: Comment Submit Route

Task card: `FP-021-comment-routes.task.md` (sole spec). Goal: add
`social_app/views_comment.py` mounting `POST /posts/<id>/comments`, and wire it
into `social_app/app.py::create_app()`. The view orchestrates four steps and
owns no persistence, validation or authorization logic:

1. login guard (FP-003 `require_login`),
2. form parse (`social_app.app.parse_form`),
3. authorization (FP-019 `authorize_interaction`),
4. comment write (FP-018 `comment_service.add_comment`),

then returns `303` to `/` (or a readable error page).

## Approach

- **One new module `social_app/views_comment.py`**, mirroring the
  `views_follow.py` orchestration style: a thin handler plus a small
  `_error_page(...)` renderer. The route pattern is the card's literal
  `/posts/<id>/comments`, so the router fills `request.params["id"]`.
- **Dependencies imported as module-level names** exactly as the card demands
  so tests can monkeypatch them (card §4/§6):
  `from social_app.comment_service import CommentError, add_comment` and
  `from social_app.interaction_service import InteractionError,
  authorize_interaction`. `require_login` / `current_user_id` come from
  `social_app.session` and are patched in the same way.
- Public contract (card §3.2):

  ```python
  def comment_submit(request) -> Response   # POST /posts/<id>/comments
  def register(app) -> None
  ```

- **Handler flow** (card §4, order preserved):

  ```python
  guard = require_login(request)
  if guard is not None:
      return guard
  post_id = int(request.params["id"])
  content = parse_form(request.body).get("content", "")
  actor_id = current_user_id(request)
  try:
      authorize_interaction(actor_id, post_id)
      add_comment(post_id, actor_id, content)
  except InteractionError as exc:
      return _error_page(str(exc))
  except CommentError as exc:
      return _error_page(str(exc))
  return redirect(HOME_PATH)
  ```

- **Error page** (card §4): status `200`, readable Chinese reason from the
  exception message, plus `<a href="/">返回首页</a>`, following the
  `views_follow._feedback_page` convention and escaping every echoed value.

## Key decisions

1. **Authorization before the write.** `authorize_interaction` runs before
   `add_comment`, so a denied actor never reaches the write path (acceptance 4
   "no write"). Since FP-019 is read-only this is also structurally safe.
2. **Login guard first.** An anonymous request short-circuits to the FP-003
   `303 /login` response before parsing or any service call (acceptance 3).
3. **Two except clauses, one renderer.** `InteractionError` and `CommentError`
   are distinct types from distinct modules; catching both and rendering the
   same readable page keeps the contract clear while avoiding duplicate HTML.
4. **No database access, no `list_comments`.** Success only redirects; the
   feed's comment list is FP-022. This module never imports `social_app.db`.
5. **No HTML form rendering.** The comment input lives in the FP-022 feed page;
   this task is submit-only, so `content` is read with `parse_form(...).get(...)`
   defaulting to `""` (the service turns blank into `CommentError`).
6. **Tests isolate both dependencies by monkeypatching** the module-level names
   (card §6), with one extra end-to-end test against a real temp DB + session to
   prove the wiring works with the landed FP-018/FP-019 implementations.

## Verification

`python3 -m pytest tests/test_fp021_comment_routes.py -q`, then the full suite.
Scenarios documented in `docs/test-cases/fp021-comment-routes.md`.
