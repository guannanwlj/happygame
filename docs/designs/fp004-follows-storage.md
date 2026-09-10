# FP-004 Design: Follow Relationship Storage

Task card: `input/tasks/social-platform-mvp/FP-004-follows-storage.task.md`
(sole spec). Goal: add a one-directional follow table `follows`
(`follower_id → followee_id`, unique) to the existing storage module and expose
read/write helpers `add_follow` / `is_following` / `list_followees` in a new
module `social_app/follows.py`. The legacy bidirectional friend tables
(`friend_requests`, `friendships`) are left untouched.

## Approach

- **Schema append only.** Add one `CREATE TABLE IF NOT EXISTS follows (...)`
  block to the existing `SCHEMA_SQL` constant in `social_app/db.py`, verbatim
  from card §3.1. `init_db` already runs the whole script, so no other change
  to `db.py` is needed and `init_db` stays idempotent.
- **New module `social_app/follows.py`.** All three helpers delegate to the
  existing generic API (`db.execute` / `db.query_one` / `db.query_all`); no
  direct `sqlite3` connection management. This keeps one connection-per-call
  semantics and honors the `SOCIAL_DB` env var automatically.
- **`add_follow` is idempotent** via `INSERT OR IGNORE`; return value is
  derived from `cursor.rowcount` (1 = inserted → `True`, 0 = already present
  → `False`), so a duplicate never raises.
- **`is_following`** uses `SELECT 1 ... LIMIT 1` and returns a bool.
- **`list_followees`** returns a plain `list[int]` of `followee_id`, ordered by
  `id` (insertion order) for stable output.
- **No validation logic.** Self-follow, non-existent target and login checks
  are explicitly FP-011 (`§5`). Foreign keys remain enabled by
  `get_connection`, so a non-existent user still triggers
  `sqlite3.IntegrityError` at the storage layer, as required by §7.

## Key decisions

1. **Reuse `db.execute` for the write**: it commits and returns the cursor,
   so `rowcount` is available to distinguish insert vs. ignore without a
   second query.
2. **No `__init__.py` re-export**: consumers import `social_app.follows`
   directly per the card contract; the package surface stays stable for
   concurrent wave-1 tasks.
3. **Ordering by `id`**: gives deterministic `list_followees` output that
   matches "A followed B then C" without depending on rowid internals beyond
   insertion order.
4. **Legacy tables untouched**: no migration, no deletion — historical
   friendship model remains as-is.

## Verification

`python3 -m pytest tests/test_fp004_follows.py -q` (plus full suite).
Scenarios documented in `docs/test-cases/fp004-follows.md`.
