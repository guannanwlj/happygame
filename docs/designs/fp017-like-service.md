# FP-017 Design: Like Service

Task card: `input/tasks/social-like-comment/FP-017-like-service.task.md` (sole
spec). Goal: add `social_app/like_service.py` exposing the idempotent business
operations `like(actor_id, post_id)` / `unlike(actor_id, post_id)` (each returns
the post's current total) and `count_likes(post_id)`.

## Approach

- **New module `social_app/like_service.py`.** Thin orchestration over the
  FP-015 storage primitives (`social_app.likes`) and the generic DB API. No
  HTTP/rendering (FP-020/FP-022) and no ownership/permission checks (FP-019).
- **Module-level imports.** Import `add_like`, `remove_like`, `is_liked` as
  module globals (`from social_app.likes import ...`) so tests and callers can
  monkeypatch them, mirroring `views_feed`'s treatment of `get_feed`.
- **`like`** calls `add_like(actor_id, post_id)` (itself idempotent via the
  `UNIQUE (user_id, post_id)` constraint + `INSERT OR IGNORE`) and then returns
  `count_likes(post_id)`. No duplicate pre-check.
- **`unlike`** calls `remove_like(actor_id, post_id)` (idempotent `DELETE`) and
  then returns `count_likes(post_id)`. Removing a missing like is not an error.
- **`count_likes`** runs `SELECT COUNT(*) AS n FROM likes WHERE post_id = ?`
  through `db.query_one` and returns the integer `n` (0 when no likes).

## Key decisions

1. **Idempotency delegated to storage.** The service adds no checks; FP-015's
   `INSERT OR IGNORE` / `DELETE` already make repeats safe. This keeps business
   rules minimal and race-safe at the DB layer.
2. **Return the fresh total after each mutation.** Callers (FP-020) can render
   the updated count without a second query, matching the card contract.
3. **`LikeError` intentionally omitted.** The card lists no validation or error
   paths for this task; unknown post/user integrity is FP-019/FP-020's concern.
   Keeping the surface to the three contract functions avoids speculative code.
4. **`is_liked` imported but unused here** is avoided; only `add_like` and
   `remove_like` are imported (the storage module exposes `is_liked` for FP-022).

## Verification

`python3 -m pytest tests/test_fp017_like_service.py -q` then the full suite.
Scenarios documented in `docs/test-cases/fp017-like-service.md`. Since FP-015 has
landed, tests use the real storage against a temp `SOCIAL_DB`; one test
monkeypatches the storage functions to prove isolation from FP-015.
