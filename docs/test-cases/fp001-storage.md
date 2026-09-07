# FP-001 Test Scenarios — Core Data Model & Persistent Storage

Module under test: `social_app/db.py` (spec: task card FP-001 §3.1/§7/§8).
Every test uses a fresh temporary DB file via the `SOCIAL_DB` env var — no
shared state, no repo pollution.

## A. Acceptance 1 — persistence across reopen (simulated restart)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Insert a user (alice, hash "h1"), close connection, reopen same file | Row present; id/username/password_hash identical; `created_at` auto-populated |
| A2 | Insert a pending friend request, reopen | Row present with all fields, status defaults to `pending`, timestamps auto-populated |
| A3 | Insert both friendship rows (a,b)+(b,a), reopen | Both rows present and identical field-wise |
| A4 | Insert a post, reopen | Row present; content/author_id identical; `created_at` auto-populated |

## B. Acceptance 2 — API covers create + query; init_db idempotent

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `init_db` on a fresh file, then inspect `sqlite_master` via the module API | All 4 tables exist (users, friend_requests, friendships, posts) |
| B2 | `init_db` executed twice (second time via passed-in connection) | No error raised (idempotent), tables still intact |
| B3 | Create users with `execute(INSERT ...)`, read with `query_all` / `query_one` | `execute` returns cursor with `.lastrowid` set; `query_all` returns all rows; `query_one` returns first row or `None` for no match |
| B4 | `get_connection` configuration | `row_factory` is `sqlite3.Row`; `PRAGMA foreign_keys` is ON (insert referencing missing user fails) |
| B5 | `db_path()` env handling | Defaults to `social_platform.db` when env unset; returns `$SOCIAL_DB` value when set |
| B6 | UNIQUE constraints work through the API | Duplicate username raises `sqlite3.IntegrityError`; second pending request in same direction raises (partial unique index) |

## C. Acceptance 3 — transaction() atomicity

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Inside `transaction()`: INSERT ok, then second INSERT raises | Exception propagates to caller; first INSERT rolled back (0 rows remain) |
| C2 | Inside `transaction()`: two INSERTs both succeed | Both rows committed and visible after the block |

## D. Edge cases / error handling

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Writing data, then changing `SOCIAL_DB` to a new file | New file independent (empty until `init_db`), old file untouched — env switch effective |
| D2 | `query_one` with no match | Returns `None` (not an error) |
| D3 | Seed scenario from card §6: alice + pending request + bidirectional friendship + post, close, reopen | All four kinds of rows survive with identical content |
| D4 | Foreign keys enforced on delete-adjacent inserts for every FK table | Insert with nonexistent requester/addressee/user/author id raises `sqlite3.IntegrityError` |
| D5 | `transaction()` yields a working connection usable with `execute`-style manual `conn.execute` | Raw connection API usable inside the block (row_factory set) |

Skeleton/test file: `tests/test_fp001_storage.py`.
