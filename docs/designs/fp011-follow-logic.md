# FP-011 Design: Follow Rule Validation & Write

Task card: `FP-011-follow-logic.task.md` (sole spec; body embedded in the work
order). Goal: add a self-contained service module `social_app/follow_service.py`
that validates a follow request (logged in, target exists, not self) and then
delegates the idempotent write to FP-004's `add_follow`.

## Approach

- One new module `social_app/follow_service.py`; no existing runtime code is
  touched. It imports the already-landed storage layer
  (`social_app.db.query_one`) and the FP-004 write helper
  (`social_app.follows.add_follow`).
- Public contract (card §3.3):

  ```python
  class FollowError(Exception):
      """关注失败，message 为面向用户的可读中文原因。"""

  def follow(actor_id: int | None, target_username: str) -> None
  ```

- Rule evaluation order (card §4), first failure wins:

  1. `actor_id is None` → `FollowError("未登录")`
  2. `SELECT id FROM users WHERE username = ?` returns no row →
     `FollowError("用户不存在")`
  3. `target_id == actor_id` → `FollowError("不能关注自己")`
  4. otherwise `add_follow(actor_id, target_id)` — idempotent, duplicate
     follows succeed silently.

- All validation failures raise before any write, so rejected requests leave
  the `follows` table untouched (card §7).

## Key decisions

1. **Service owns rules, storage owns rows.** `follow_service` never touches
   the `follows` table directly; it queries `users` by username only and then
   calls `add_follow`. This keeps the one-directional write semantics and the
   idempotence guarantee in one place (FP-004).
2. **`FollowError` subclasses `Exception`.** A dedicated type lets the caller
   (FP-010) distinguish a user-facing rule violation from unexpected errors and
   render `str(exc)` directly as the message.
3. **Username lookup precedes the self check.** The card validates own-account
   follows via the target *username* (`follow(A, "alice")`), so the id must be
   resolved before it can be compared with `actor_id`.
4. **No write on any failure path.** Self-follow and unknown-target requests
   raise before `add_follow`, avoiding self-loop and reverse records (card §4).
5. **Thin module, no web concerns.** No page, route, redirect or response
   handling — that is FP-010. `actor_id` is supplied by the caller from
   `session.current_user_id`; this module only agrees that `None` means
   anonymous.

## Verification

`python3 -m pytest tests/test_fp011_follow_service.py -q` (plus the full
suite `python3 -m pytest -q`). Scenarios documented in
`docs/test-cases/fp011-follow-logic.md`.
