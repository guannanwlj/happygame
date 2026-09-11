# FP-016 Design: Comment Data & Storage

Task card: `input/tasks/social-like-comment/FP-016-comment-storage.task.md`
(sole spec). Goal: append a `comments` table to `social_app/db.py::SCHEMA_SQL`
and add `social_app/comments.py` exposing two thin storage helpers —
`add_comment(post_id, author_id, content) -> int` and
`list_comments(post_id) -> list[sqlite3.Row]` (ascending by `created_at`,
tie-broken by `id`).

## Approach

- **Schema append only.** Add one `CREATE TABLE IF NOT EXISTS comments (...)`
  block plus `CREATE INDEX IF NOT EXISTS idx_comments_post` to the existing
  `SCHEMA_SQL` constant, verbatim from card §3.1. `init_db` already executes
  the whole script, so `db.py` needs no other change and stays idempotent.
  Existing tables (`users`, `posts`, `follows`, …) are untouched.
- **New module `social_app/comments.py`.** Both helpers delegate to the
  existing generic API (`db.execute` / `db.query_all`); no direct `sqlite3`
  connection management, so the `SOCIAL_DB` env var is honored automatically.
- **`add_comment`** runs a single `INSERT` through `db.execute` (which commits)
  and returns `cursor.lastrowid` — the new comment id.
- **`list_comments`** runs
  `SELECT id, post_id, author_id, content, created_at FROM comments
   WHERE post_id = ? ORDER BY created_at ASC, id ASC`
  and returns the raw `sqlite3.Row` list, matching the §3.2 contract (at
  least the five named columns).
- **No validation logic.** Empty/whitespace-only content checks, readable
  errors, ownership checks, HTTP entry and feed rendering are explicitly out
  of scope (§5) and belong to FP-018/FP-019/FP-021/FP-022. This module is a
  pure write/read boundary.

## Key decisions

1. **Persist `created_at` via the DDL default** (`strftime(...'now')`), so the
   write helper stays a plain single-column INSERT and the timestamp format is
   consistent with every other table in the schema.
2. **Tie-break on `id`.** SQLite's `'%f'` timestamp has millisecond precision,
   so same-millisecond inserts share `created_at`; `ORDER BY created_at ASC,
   id ASC` guarantees a deterministic ascending order as required by §7.
3. **Explicit column list in the SELECT** rather than `SELECT *` — locks the
   contract columns and keeps output stable if the table gains columns later.
4. **Foreign keys are enforced** because `get_connection` sets
   `PRAGMA foreign_keys = ON`, so commenting on a missing post/user raises
   `sqlite3.IntegrityError` at the storage layer.
5. **No `__init__.py` re-export**: consumers import `social_app.comments`
   directly per the card contract, keeping the package surface stable for
   concurrent wave-1 tasks.

## Verification

`python3 -m pytest tests/test_fp016_comments.py -q` then the full
`python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp016-comments.md`.
