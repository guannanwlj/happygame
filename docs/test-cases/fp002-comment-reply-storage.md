# FP-002 Test Scenarios — Comment Reply Relation Storage

Modules under test: the `comments` table and `init_db` upgrade in
`social_app/db.py`, and `social_app/comments.py`
(spec: task card FP-002 §3.1/§3.2/§7/§8). Every test uses a fresh temporary
DB file via the `SOCIAL_DB` env var — no shared state, no repo pollution.

## A. Acceptance 1 — top-level comment

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `add_comment(post, author, content)` with no `parent_id` | Stored row has `parent_id IS NULL` |
| A2 | Same call | Backward-compatible: still returns the new integer id |
| A3 | `get_comment(id)` on a top-level comment | `parent_id` is `None` |

## B. Acceptance 2 — reply to a top-level comment

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Top-level `c1`; `add_comment(post, author, content, parent_id=c1)` | Returns `c2`; row's `parent_id == c1` |
| B2 | `get_comment(c2)` | Row has `parent_id == c1` |
| B3 | `parent_id=None` explicitly | Same as omitted (top-level) |

## C. Acceptance 3 — legacy database upgrade

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Build an old-schema DB (no `parent_id`), insert a comment, run upgraded `init_db()` | `PRAGMA table_info(comments)` now lists `parent_id` |
| C2 | Same legacy row after upgrade | Still readable; `parent_id IS NULL` |
| C3 | New reply on the upgraded DB | `parent_id` stores the parent id |

## D. Acceptance 4 — list ordering and columns

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Post with top-level + reply at distinct `created_at` (seeded out of order) | `list_comments` returns oldest → newest |
| D2 | Same `created_at`, different ids | Tie broken by `id` ascending |
| D3 | Rows returned by `list_comments` | Include `parent_id` alongside the existing contract columns |
| D4 | Post with no comments | `[]` |

## E. Edge cases / error handling

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Reply referencing a missing parent id | Raises `sqlite3.IntegrityError` (FK enforced) |
| E2 | `get_comment` on a missing id | Returns `None` |
| E3 | Blank content stored via storage layer | Stored verbatim (validation is FP-018) |
| E4 | Missing post/author | `sqlite3.IntegrityError` (unchanged, regression) |

## F. Acceptance 5 — idempotency & regression

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `init_db()` run repeatedly, including explicit `conn` | No error; no duplicate column; data survives |
| F2 | Existing two-arg `add_comment` usage (FP-016/FP-018) | Unchanged behaviour |
| F3 | Legacy tables and columns after the upgrade | `users`/`posts` and existing `comments` columns intact |

Skeleton/test file: `tests/test_fp002_comment_reply_storage.py`.
