# FP-003 Design: Comment Interaction Authorization

Task card: `FP-003-comment-interaction-authorization.task.md` (sole spec).
Goal: extend the existing post interaction guard so callers can ask "may this
user interact with this comment?". The check first resolves the comment's post
and then reuses the existing post authorization口径; it is read-only and raises
a readable Chinese `InteractionError` on every denial.

## Approach

- **Extend `social_app/interaction_service.py`** (already home to
  `InteractionError` and `authorize_interaction`). No new module, no schema
  change: `posts`, `follows` and `comments` already exist in
  `social_app/db.py::SCHEMA_SQL`.
- Public contract (card §3.2):

  ```python
  COMMENT_NOT_FOUND_MESSAGE = "评论不存在"

  def authorize_comment_interaction(actor_id: int | None, comment_id: int) -> None:
      """通过则返回 None；否则抛 InteractionError，且不产生任何写入。"""
  ```

- **Ordered checks** (card §4):
  1. Resolve the comment's post:
     `SELECT post_id FROM comments WHERE id = ?`; no row →
     `InteractionError("评论不存在")`.
  2. Delegate to `authorize_interaction(actor_id, post_id)` for the
     login / author / follower decision, propagating its `InteractionError`.
- **Read-only by construction.** Only `db.query_one` is called (directly and
  inside `authorize_interaction` / `is_following`); there is no
  `INSERT`/`UPDATE`/`DELETE` and no `db.execute`.
- Error text lives in the module constant `COMMENT_NOT_FOUND_MESSAGE` so tests
  and future routes (FP-004) share one source of truth.

## Key decisions

1. **Inline comment lookup, not `comments.get_comment`.** The card §3.2 names
   `comments.get_comment` as an FP-002 deliverable and §6 says to fall back to
   an inline `SELECT id, post_id FROM comments WHERE id = ?` when it is absent.
   FP-002 is not present in this repo yet, so this task owns the inline query
   and reads only the `post_id` column it needs (no `parent_id` dependency).
2. **Existence before login.** The card lists the comment lookup as step 1 and
   delegation as step 2, so a missing comment yields "评论不存在" even for an
   anonymous actor; an existing comment delegates and yields "未登录".
3. **Reuse `authorize_interaction` wholesale** rather than duplicating the
   author/follower logic, keeping the post-level口径 the single source of truth
   (card §4 "复用").
4. **Return `None` implicitly on success**, matching the documented contract and
   `authorize_interaction`.
5. **No HTTP/route work.** FP-004 owns the comment interaction route;
   `social_app/session.py::require_login` stays where it is.

## Verification

`python3 -m pytest tests/test_fp003_comment_authorization.py -q`, then the full
suite. Scenarios documented in
`docs/test-cases/fp003-comment-interaction-authorization.md`.
