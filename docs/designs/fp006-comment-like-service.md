# FP-006 Design: Comment Like Service

Task card: `input/tasks/social-comment-interactions/FP-006-comment-like-rules.task.md`
(sole spec). Goal: add `social_app/comment_like_service.py` exposing the
idempotent business operations `like_comment(actor_id, comment_id)` /
`unlike_comment(actor_id, comment_id)` (each returns the comment's current
total) and `count_comment_likes(comment_id)`.

## Approach

- **New module `social_app/comment_like_service.py`.** Thin orchestration over
  the FP-001 storage primitives in `social_app.comment_likes` and the generic DB
  API. No HTTP/rendering (FP-004/FP-005) and no authorization checks (FP-003).
- **Module-level imports.** Import `add_comment_like`, `remove_comment_like`,
  and `count_comment_likes` as module globals so tests and callers can
  monkeypatch them, mirroring `social_app/like_service.py`.
- **`like_comment`** calls `add_comment_like(actor_id, comment_id)` (itself
  idempotent via the `UNIQUE (user_id, comment_id)` constraint plus
  `INSERT OR IGNORE`) and then returns `count_comment_likes(comment_id)`. No
  duplicate pre-check and no self-like guard (D6 allows self-likes).
- **`unlike_comment`** calls `remove_comment_like(actor_id, comment_id)`
  (idempotent `DELETE`) and then returns `count_comment_likes(comment_id)`.
  Removing a missing like is not an error.
- **`count_comment_likes`** re-exports the storage primitive, which runs
  `SELECT COUNT(*) AS n FROM comment_likes WHERE comment_id = ?` and returns the
  integer `n` (0 when no likes).

## Key decisions

1. **Idempotency delegated to storage.** The service adds no checks; FP-001's
   `INSERT OR IGNORE` / `DELETE` already make repeats safe, keeping the business
   rules minimal and race-safe at the DB layer.
2. **Return the fresh total after each mutation.** Callers (FP-004) render the
   updated count without a second query, matching the card §3.2 contract.
3. **Self-like allowed.** Per D6 the service deliberately omits any
   "cannot like your own comment" restriction.
4. **`count_comment_likes` is a direct re-export.** Unlike `like_service`
   (which adds its own SQL), the card §4 says to "transparently pass through"
   the FP-001 counter; re-exporting keeps the count logic in one place and still
   lets tests monkeypatch the name on the service module.
5. **Independent from post likes.** The service only ever touches
   `comment_likes`; the post `likes` table is untouched (D8).

## Verification

`python3 -m pytest tests/test_fp006_comment_like_service.py -q` then the full
suite. Scenarios documented in `docs/test-cases/fp006-comment-like-service.md`.
FP-001 has landed, so tests use the real storage against a temp `SOCIAL_DB`;
one test monkeypatches the storage functions to prove isolation from FP-001.
