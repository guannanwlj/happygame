# FP-019 Design: Interaction Authorization Guard

Task card: `FP-019-interaction-authorization.task.md` (sole spec). Goal: add
`social_app/interaction_service.py` exposing a shared "can this user interact
with this post?" safety rule for the like entry point (FP-020) and the comment
entry point (FP-021). The check is pure: it decides and either returns `None`
or raises a user-facing `InteractionError`, and never writes.

## Approach

- **One new module `social_app/interaction_service.py`**, mirroring the
  thin-service style of `social_app/follow_service.py` (rules module) and
  `social_app/posts.py` (`XxxError` + storage delegation). No schema change:
  the `posts` and `follows` tables already exist in
  `social_app/db.py::SCHEMA_SQL`, and `follows.is_following` already exists.
- **Dependencies imported at module level** exactly as the card demands, so
  callers/tests can monkeypatch the module-level names:
  `from social_app import db` and `from social_app.follows import is_following`.
- Public contract (card §3.2):

  ```python
  class InteractionError(Exception):
      """互动被拒，message 为面向用户的可读中文原因。"""

  def authorize_interaction(actor_id: int | None, post_id: int) -> None:
      """通过则返回 None；否则抛 InteractionError，且不产生任何写入。"""
  ```

- **Ordered checks** (card §4, order matters for the anon/missing cases):
  1. `SELECT author_id FROM posts WHERE id = ?`; no row →
     `InteractionError("帖子不存在")`.
  2. `actor_id is None` → `InteractionError("未登录")` (defensive; routes
     normally guard login first).
  3. `author_id == actor_id` → return (author may always interact).
  4. `is_following(actor_id, author_id)` is true → return (follower allowed).
  5. otherwise → `InteractionError("无权互动该帖子")`.
- **Read-only by construction.** Only `db.query_one` is called; there is no
  `INSERT`/`UPDATE`/`DELETE` and no `db.execute`. The "no write on denial"
  acceptance is therefore structural, not rollback-based.
- Error text lives in module constants so tests and future callers share one
  source of truth.

## Key decisions

1. **Existence before login.** The card lists the post lookup as step 1 and
   the anonymous guard as step 2, so a nonexistent post yields "帖子不存在"
   even for an anonymous actor. Follow the card literally.
2. **No comment table dependency.** §7 mentions `comments` among the tables
   with "no new rows", but no `comments` table exists in `db.py` yet (FP-018
   owns it). Tests snapshot **all** tables present in `sqlite_master` before
   and after a denied call, so the assertion holds with or without a `comments`
   table once FP-018 lands.
3. **Return `None` explicitly on success** (bare `return`), matching the
   documented contract and making the two allow paths symmetric.
4. **No `__init__.py` re-export.** Consumers import `social_app.interaction_service`
   directly, keeping the package surface stable for concurrent wave-2 tasks.
5. **No HTML rendering / redirects.** Wholly out of scope; FP-020/FP-021 render
   the error page from `InteractionError`'s message.

## Verification

`python3 -m pytest tests/test_fp019_interaction_guard.py -q`, then the full
suite. Scenarios documented in
`docs/test-cases/fp019-interaction-authorization.md`.
