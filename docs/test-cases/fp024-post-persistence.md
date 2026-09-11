# FP-024 Test Scenarios — Post Persistence Module

Module under test: `social_app/posts.py` (`PostError`, `create_post`) against
the existing `posts` table (spec: task card FP-024 §3.2/§4/§7/§8). Every test
uses a fresh temporary DB file via the `SOCIAL_DB` env var, calls
`db.init_db()`, then seeds one user — no shared state, no repo pollution.

## A. Acceptance 1 — normal post persists

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Seeded user; `create_post(user, "hello")` | Returns a new positive `int` id |
| A2 | After A1 | Exactly one `posts` row exists with `author_id == user` and `content == "hello"` |
| A3 | `create_post` return value | Equals the inserted row's `id` |

## B. Acceptance 2 — returns an int id

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Normal content | Return type is exactly `int` (`type(...) is int`), no exception |
| B2 | Second post after the first | Id is greater than the first (auto-increment) |

## C. Acceptance 3 — blank content rejected without writing

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `create_post(user, "   ")` | Raises `PostError`; `posts` row count unchanged (0) |
| C2 | `create_post(user, "\n\t")` | Raises `PostError`; row count unchanged |
| C3 | `create_post(user, "")` | Raises `PostError`; row count unchanged |
| C4 | Existing row then `create_post(user, "  ")` | Raises `PostError`; still exactly one row |
| C5 | Error message | Human-readable Chinese, `"帖子内容不能为空"` |

## D. Acceptance 4 — FP-012 caller contract

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `from social_app import posts` | `posts.create_post` and `posts.PostError` both exist and are callable/raisable |
| D2 | `PostError` is an `Exception` subclass | `issubclass(posts.PostError, Exception)` is `True` |
| D3 | `views_post._load_posts()` resolves the module | Returns the same `social_app.posts` module |

## E. Edge cases / integrity

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Content with surrounding whitespace (`"  hi  "`) | Stored unchanged (trim is only the non-empty check); row exists |
| E2 | Non-existent author id | Raises `sqlite3.IntegrityError` (FK constraint) |
| E3 | `init_db` idempotent after posts exist | `posts` row survives a second `db.init_db()` |

Skeleton/test file: `tests/test_fp024_posts.py`.
