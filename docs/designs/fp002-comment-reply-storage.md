# FP-002 Design: Comment Reply Relation Storage

Task card: `input/tasks/social-comment-interactions/FP-002-comment-reply-storage.task.md`
(sole spec). Goal: add a nullable self-reference `parent_id` to the existing
`comments` table, upgrade legacy databases in place, and extend
`social_app/comments.py` with `add_comment(..., parent_id=None)` and
`get_comment(comment_id)`, while `list_comments` also returns `parent_id`.

## Approach

- **Schema evolution, not replacement.** Append
  `parent_id INTEGER REFERENCES comments(id)` to the `comments` block in
  `social_app/db.py::SCHEMA_SQL`. Because `init_db` uses
  `CREATE TABLE IF NOT EXISTS`, an existing database gains nothing from the
  new DDL; a dedicated upgrade step is required.
- **Explicit, idempotent upgrade step in `init_db`.** After running the
  schema script, read `PRAGMA table_info(comments)` and, when `parent_id` is
  absent, run
  `ALTER TABLE comments ADD COLUMN parent_id INTEGER REFERENCES comments(id)`.
  SQLite allows `ADD COLUMN` with `REFERENCES` and backfills existing rows as
  `NULL`, which is exactly the "top-level comment" semantics. Re-running
  `init_db` sees the column present and does nothing.
- **Single code path for both connection modes.** A private
  `_upgrade_schema(conn)` helper operates on whatever connection `init_db`
  is using (own connection or caller-supplied), keeping the two branches
  identical.
- **`comments.py` extension.** `add_comment` gains a keyword-with-default
  `parent_id: int | None = None` and writes it on the INSERT; `get_comment`
  is a new single-row SELECT; `list_comments` simply adds `parent_id` to its
  existing explicit column list. Ordering (`created_at ASC, id ASC`) and the
  two-argument `add_comment` call form stay unchanged.
- **Store only, do not validate.** Reply-level rules (one level only, parent
  must exist, parent post match) and content checks belong to FP-008/FP-018
  (§5). Foreign keys still raise `sqlite3.IntegrityError` for a missing
  parent, same as for `post_id`/`author_id`.

## Key decisions

1. **`PRAGMA`/`ALTER` rather than a migration table.** The schema is a single
   `SCHEMA_SQL` constant and the project has no migration framework; a
   targeted column check is the smallest change that satisfies the
   compatibility acceptance criterion.
2. **Backfill defaults to `NULL`.** Existing comments are top-level by
   definition; no data rewriting is needed.
3. **`parent_id` is nullable and has no `CHECK`.** The card specifies exactly
   `parent_id INTEGER REFERENCES comments(id)`; level/content validation is
   out of scope.
4. **`get_comment` returns the raw `sqlite3.Row`** (or `None`), consistent
   with the raw-row contract of `list_comments` and the rest of the storage
   layer.
5. **Explicit column lists** in both SELECTs lock the contract columns and
   stay stable if the table gains columns later.

## Verification

`python3 -m pytest tests/test_fp002_comment_reply_storage.py -q` then the
full `python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp002-comment-reply-storage.md`.
