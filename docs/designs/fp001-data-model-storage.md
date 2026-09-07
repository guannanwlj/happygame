# FP-001 Design: Core Data Model & Persistent Storage

Task card: `input/tasks/social-platform/FP-001-data-model-storage.task.md` (sole spec).
Goal: SQLite persistence module `social_app/db.py` for the four core tables
(users, friend_requests, friendships, posts) plus a generic access API, so all
later feature tasks (FP-002..FP-011) read/write through this module.

## Approach

- New package `social_app/` with a single module `social_app/db.py`; stdlib
  `sqlite3` only (no third-party deps — Flask wiring arrives in FP-002).
- DDL from the task card §3.1 is kept verbatim as the module constant
  `SCHEMA_SQL` (single `executescript`-able script, all statements use
  `IF NOT EXISTS` so `init_db` is idempotent).
- Database file location resolved per call via `db_path()`:
  `$SOCIAL_DB` if set, else `social_platform.db`. Env var is read at call
  time (not import time) so tests can point each test at a fresh tmp file
  with `monkeypatch.setenv`.
- `get_connection()` opens a new `sqlite3.connect(db_path())` connection with
  `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`; callers own
  closing (`contextlib.closing` recommended). One connection per operation
  keeps the module stateless and thread-safe enough for the dev server.
- `query_all` / `query_one` are read helpers; `execute` runs a single
  INSERT/UPDATE/DELETE and commits before returning the cursor (so
  `.lastrowid` / `.rowcount` stay usable).
- `transaction()` is a `@contextlib.contextmanager` yielding one dedicated
  connection: COMMIT on clean exit, ROLLBACK on exception — for multi-statement
  atomic writes (e.g. inserting both friendship rows).

## Key decisions

1. **Read env at call time**: makes `SOCIAL_DB` switching trivial in tests and
   avoids import-order hazards.
2. **`init_db(conn=None)` convenience**: when given a connection it uses it
   (caller closes); otherwise opens/closes its own — matches the contract in
   the card and helps tests that want a scripted init inside a transaction.
   `executescript` issues an implicit COMMIT first, which is fine because
   init is standalone.
3. **No business logic**: no password hashing, no friendship rules — those are
   FP-003/FP-008. This module is pure storage.
4. **Durability**: SQLite journal + commit on every write satisfies the
   "restart does not lose data" acceptance; tests simulate restart by closing
   all connections and reopening the same file.
5. **Partial index `uq_fr_pending`** requires SQLite ≥ 3.8 (system 3.4x) —
   kept as-is per the card.

## Verification

`python3 -m pytest tests/test_fp001_storage.py -q` (plus full suite).
Scenarios documented in `docs/test-cases/fp001-storage.md`.
