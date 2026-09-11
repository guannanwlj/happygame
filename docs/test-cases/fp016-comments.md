# FP-016 Test Scenarios — Comment Data & Storage

Modules under test: `social_app/comments.py` (helpers) and the `comments`
table added to `social_app/db.py` (spec: task card FP-016 §3.1/§3.2/§7/§8).
Every test uses a fresh temporary DB file via the `SOCIAL_DB` env var — no
shared state, no repo pollution.

## A. Acceptance 1 — schema creation

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Empty DB; `db.init_db()` | `comments` table exists with columns `id`, `post_id`, `author_id`, `content`, `created_at` |
| A2 | Inspect the table | `post_id` and `author_id` are `NOT NULL` foreign keys to `posts(id)` / `users(id)`; `created_at` `NOT NULL` |
| A3 | Re-run `db.init_db()` | No error; table still present (idempotent, `IF NOT EXISTS`) |

## B. Acceptance 2 — add a comment

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Seed post P, author A; `add_comment(P, A, "hello")` | Returns a new integer id |
| B2 | Read back the row | Row has `post_id=P`, `author_id=A`, `content="hello"`, non-empty `created_at` |
| B3 | Add two comments | ids are distinct and increasing |

## C. Acceptance 3 — list ordered ascending

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Post P with comments created at distinct `created_at` (seeded explicitly) | `list_comments(P)` returns them oldest → newest |
| C2 | Same `created_at`, different ids | Tie broken by `id` ascending |
| C3 | Comments on another post Q | Never included in `list_comments(P)` |
| C4 | Returned rows | Are `sqlite3.Row` with at least `id`, `post_id`, `author_id`, `content`, `created_at` |

## D. Acceptance 4 — empty result

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Post P has no comments; `list_comments(P)` | `[]` (a `list`, not `None`) |

## E. Edge cases / error handling

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `add_comment` on missing post or missing author | Raises `sqlite3.IntegrityError` (FK enforced) |
| E2 | Empty/whitespace content | Stored as-is (no validation here — FP-018 owns it) |
| E3 | `created_at` default populated by the DB | Non-null when the helper omits it |
| E4 | `init_db` twice keeps existing comments | Rows survive a repeat schema apply |

## F. Regression / hygiene

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Legacy tables after adding `comments` | `users`, `posts`, `follows`, `friend_requests`, `friendships` still exist |
| F2 | Existing `posts` columns unchanged | `posts(id, author_id, content, created_at)` intact |

Skeleton/test file: `tests/test_fp016_comments.py`.
