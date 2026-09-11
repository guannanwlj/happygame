# FP-015 Test Scenarios — Like Data & Storage

Modules under test: `social_app/likes.py` (storage primitives) and the `likes`
table added to `social_app/db.py` (spec: task card FP-015 §3.1/§3.2/§7/§8).
Every test uses a fresh temporary DB file via the `SOCIAL_DB` env var — no
shared state, no repo pollution. Seed: two users (`users(username,
password_hash)`) and two posts (`posts(author_id, content)`).

## A. Acceptance 1 — schema creation

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Empty DB; `db.init_db()` | `likes` table exists in `sqlite_master` |
| A2 | Inspect table DDL / indexes | `UNIQUE(user_id, post_id)` is enforced (duplicate raw INSERT raises `IntegrityError`) |
| A3 | Legacy tables after adding `likes` | `users`, `posts`, `follows`, `friend_requests`, `friendships` still present and unchanged |

## B. Acceptance 2 — add_like insert + idempotence

| # | Scenario | Expected |
|---|----------|----------|
| B1 | A not liking P; `add_like(A, P)` | Returns `True`; exactly one `(A,P)` row |
| B2 | `(A,P)` present; `add_like(A, P)` again | Returns `False`; still exactly one row; no exception |
| B3 | B also likes P | Returns `True`; two rows for P, one per user |

## C. Acceptance 3 — remove_like delete + idempotence

| # | Scenario | Expected |
|---|----------|----------|
| C1 | A likes P; `remove_like(A, P)` | Returns `True`; row removed |
| C2 | `(A,P)` absent; `remove_like(A, P)` again | Returns `False`; no exception |
| C3 | Removing A's like does not affect B's like on P | Only `(A,P)` removed |

## D. Acceptance 4 — is_liked

| # | Scenario | Expected |
|---|----------|----------|
| D1 | A not liking P; `is_liked(A, P)` | `False` |
| D2 | After `add_like(A, P)` | `True` |
| D3 | After `remove_like(A, P)` | `False` again |
| D4 | Directionality across users | `is_liked(B, P)` `False` when only A liked P |

## E. Edge cases / error handling

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Return types are plain `bool` | `is True` / `is False` |
| E2 | Persistence across reopen: `init_db()` again after a like | Like still present; row count stable (schema idempotent) |
| E3 | Foreign keys: `add_like` for non-existent user/post | Raises `sqlite3.IntegrityError` |
| E4 | Repeated `init_db()` keeps `likes` table present | No error, table still there |

Skeleton/test file: `tests/test_fp015_likes.py`.
