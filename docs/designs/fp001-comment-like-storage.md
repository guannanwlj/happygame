# FP-001 Design: Comment Like Data & Storage

Task card: `input/tasks/social-comment-interactions/FP-001-comment-like-storage.task.md`
(sole spec). Goal: add an independent `comment_likes` table (`user_id → comment_id`,
unique) to the existing storage module and expose four storage primitives
(`add_comment_like` / `remove_comment_like` / `is_comment_liked` /
`count_comment_likes`) in a new module `social_app/comment_likes.py`. The existing
`likes` table and all other tables are left untouched.

## Approach

- **Schema append only.** Add one `CREATE TABLE IF NOT EXISTS comment_likes (...)`
  block to the existing `SCHEMA_SQL` constant in `social_app/db.py`, verbatim from
  card §3.1, placed after the existing `comments` table definition. `init_db`
  already runs the whole script, so no other change to `db.py` is needed and
  `init_db` stays idempotent.
- **New module `social_app/comment_likes.py`.** All four helpers delegate to the
  existing generic API (`db.execute` / `db.query_one`); no direct `sqlite3`
  connection management. One connection-per-call semantics and the `SOCIAL_DB`
  env var are honored automatically. This mirrors the `social_app/likes.py`
  thin-storage-module precedent.
- **`add_comment_like` is idempotent** via `INSERT OR IGNORE`; the return value
  comes from `cursor.rowcount` (1 = inserted → `True`, 0 = already present →
  `False`), so a duplicate never raises.
- **`remove_comment_like` is idempotent** via `DELETE`; `cursor.rowcount == 1`
  means a row was deleted → `True`, otherwise `False` with no error.
- **`is_comment_liked`** uses `SELECT 1 ... LIMIT 1` and returns a plain `bool`.
- **`count_comment_likes`** uses `SELECT COUNT(*)` and returns `int` (0 when
  absent), independent from the post `likes` count.
- **No business logic.** Count increment/decrement orchestration and idempotency
  rules are FP-006; comment record read/write is FP-002; authorization is FP-003;
  HTTP routes are FP-004. Foreign keys stay enabled by `get_connection`, so a
  non-existent user/comment still raises `sqlite3.IntegrityError` at the storage
  layer.

## Key decisions

1. **Independent table, not a reuse of `likes`**: post likes and comment likes
   have separate counters; `comment_likes` references `comments(id)` instead of
   `posts(id)`.
2. **Reuse `db.execute` for writes**: it commits and returns the cursor, so
   `rowcount` distinguishes insert vs. ignore (and delete vs. no-op) without a
   second query.
3. **UNIQUE as the idempotency source of truth**: `UNIQUE (user_id, comment_id)`
   plus `INSERT OR IGNORE` guarantees at most one like per user/comment even
   under races; the Python layer carries no duplicate-check query.
4. **No `__init__.py` re-export**: consumers import `social_app.comment_likes`
   directly per the card contract, keeping the package surface stable for
   concurrent wave-1 tasks.
5. **Legacy tables untouched**: no migration, no deletion; `likes` rows are not
   read or written by this module.

## Verification

`python3 -m pytest tests/test_fp001_comment_like_storage.py -q` (plus full suite).
Scenarios documented in `docs/test-cases/fp001-comment-likes.md`.
