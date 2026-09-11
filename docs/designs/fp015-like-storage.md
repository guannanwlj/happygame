# FP-015 Design: Like Data & Storage

Task card: `input/tasks/social-like-comment/FP-015-like-storage.task.md` (sole
spec). Goal: add a `likes` table (`user_id → post_id`, unique) to the existing
storage module and expose the three storage primitives `add_like` / `remove_like`
/ `is_liked` in a new module `social_app/likes.py`. The existing tables
(`users`, `friend_requests`, `friendships`, `posts`, `follows`) are left
untouched.

## Approach

- **Schema append only.** Add one `CREATE TABLE IF NOT EXISTS likes (...)`
  block to the existing `SCHEMA_SQL` constant in `social_app/db.py`, verbatim
  from card §3.1. `init_db` already runs the whole script, so no other change
  to `db.py` is needed and `init_db` stays idempotent.
- **New module `social_app/likes.py`.** All three helpers delegate to the
  existing generic API (`db.execute` / `db.query_one`); no direct `sqlite3`
  connection management. One connection-per-call semantics and the `SOCIAL_DB`
  env var are honored automatically. This mirrors the `social_app/follows.py`
  thin-storage-module precedent.
- **`add_like` is idempotent** via `INSERT OR IGNORE`; return value is derived
  from `cursor.rowcount` (1 = inserted → `True`, 0 = already present → `False`),
  so a duplicate never raises.
- **`remove_like` is idempotent** via `DELETE`; `cursor.rowcount == 1` means a
  row was deleted → `True`, otherwise `False` with no error.
- **`is_liked`** uses `SELECT 1 ... LIMIT 1` and returns a plain `bool`.
- **No business logic.** Total-count aggregation and like/unlike orchestration
  are explicitly FP-017; ownership/integrity checks belong to FP-019; HTTP
  entry/routes to FP-020. Foreign keys stay enabled by `get_connection`, so a
  non-existent user/post still raises `sqlite3.IntegrityError` at the storage
  layer.

## Key decisions

1. **Reuse `db.execute` for writes**: it commits and returns the cursor, so
   `rowcount` distinguishes insert vs. ignore (and delete vs. no-op) without a
   second query.
2. **UNIQUE as the idempotency source of truth**: `UNIQUE (user_id, post_id)`
   plus `INSERT OR IGNORE` guarantees at most one like per user/post even under
   races; the Python layer carries no duplicate-check query.
3. **No `__init__.py` re-export**: consumers import `social_app.likes` directly
   per the card contract, keeping the package surface stable for concurrent
   wave-1 tasks.
4. **Legacy tables untouched**: no migration, no deletion.

## Verification

`python3 -m pytest tests/test_fp015_likes.py -q` (plus full suite). Scenarios
documented in `docs/test-cases/fp015-likes.md`.
