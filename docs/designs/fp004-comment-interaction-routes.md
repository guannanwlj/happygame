# FP-004 Design: Comment Interaction Submit Routes

Task card: `FP-004-comment-interaction-routes.task.md` (sole spec). Goal: add
`social_app/views_comment_interaction.py` mounting three comment-dimension POST
routes and wire it into `social_app/app.py::create_app()`:

| Route | Handler | Service |
|-------|---------|---------|
| `POST /comments/<id>/like` | `comment_like_submit` | `like_comment(actor_id, comment_id)` |
| `POST /comments/<id>/unlike` | `comment_unlike_submit` | `unlike_comment(actor_id, comment_id)` |
| `POST /comments/<id>/replies` | `comment_reply_submit` | `add_reply(parent_id, actor_id, content)` |

The module owns HTTP orchestration only — no persistence, validation or
authorization rules — mirroring `views_like.py` / `views_comment.py`.

## Approach

- **One new module `social_app/views_comment_interaction.py`**. It follows the
  established order: login guard (FP-003 `require_login`) → interaction
  authorization (FP-003 `authorize_comment_interaction`) → service call → `303`
  redirect to `/`, with a readable error page on denial/rejection.
- **Module-level dependency names** so tests can monkeypatch them (card §6):
  `require_login` / `current_user_id` (session), `authorize_comment_interaction`
  / `InteractionError` (interaction_service, landed with FP-003), `like_comment`
  / `unlike_comment` (FP-006) and `add_reply` / `ReplyError` (FP-008).
- **§6 fallbacks for the not-yet-landed services.** FP-006 and FP-008 are
  sibling tasks; until their modules exist the router keeps working via
  `try: from ... import ... except ImportError:` fallbacks:
  - like/unlike fall back to FP-001's `comment_likes` storage primitives
    (`add_comment_like` / `remove_comment_like` / `count_comment_likes`);
  - reply falls back to an inline `ReplyError` plus a rule that checks the
    parent exists, is top-level and has non-blank content, then writes through
    `comments.add_comment(parent_id=...)` using the parent's `post_id`.
  The fallback signatures match the real contracts, so when FP-006/FP-008 land
  the real module is imported automatically (no call-site change).
- Public contract (card §3.2):

  ```python
  COMMENT_LIKE_PATH   = "/comments/<id>/like"
  COMMENT_UNLIKE_PATH = "/comments/<id>/unlike"
  COMMENT_REPLY_PATH  = "/comments/<id>/replies"

  def comment_like_submit(request) -> Response
  def comment_unlike_submit(request) -> Response
  def comment_reply_submit(request) -> Response
  def register(app) -> None
  ```

- **Handler flows** (card §4):

  ```python
  # like / unlike
  guard = require_login(request)
  if guard is not None:
      return guard
  comment_id = int(request.params["id"])
  actor_id = current_user_id(request)
  try:
      authorize_comment_interaction(actor_id, comment_id)
      like_comment(actor_id, comment_id)          # or unlike_comment
  except InteractionError as exc:
      return _error_page(exc)
  return redirect("/")

  # reply
  guard = require_login(request)
  if guard is not None:
      return guard
  parent_id = int(request.params["id"])
  content = parse_form(request.body).get("content", "")
  actor_id = current_user_id(request)
  try:
      authorize_comment_interaction(actor_id, parent_id)
      add_reply(parent_id, actor_id, content)
  except (InteractionError, ReplyError) as exc:
      return _error_page(exc)
  return redirect("/")
  ```

## Key decisions

1. **Authorization before the write.** The FP-003 gate runs before the service
   call, so a denied actor never reaches the write path (acceptance "no write").
2. **Login guard first.** Anonymous requests short-circuit to `303 /login`
   before parsing or any service call.
3. **One readable error renderer.** `InteractionError` (denied) and
   `ReplyError` (service rejected) both mean "the submit was refused with a
   readable reason"; catching them together renders the same page with a
   `返回首页` link and `html.escape`-d values.
4. **No database access.** Success only redirects; the like/reply UI is
   FP-005/FP-007 and never rendered here. This module does not import
   `social_app.db`.
5. **Fallback modules keep the router independently runnable** while sibling
   tasks are in flight, exactly as the card §6 demands.

## Verification

`python3 -m pytest tests/test_fp004_comment_interaction_routes.py -q`, then the
full suite. Scenarios documented in
`docs/test-cases/fp004-comment-interaction-routes.md`.
