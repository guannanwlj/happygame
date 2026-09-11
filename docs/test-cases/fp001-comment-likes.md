# FP-001 Test Scenarios — Comment Like Data & Storage

Modules under test: `social_app/comment_likes.py` (storage primitives) and the
`comment_likes` table added to `social_app/db.py` (spec: task card FP-001
§3.1/§3.2/§7/§8). Every test uses a fresh temporary DB file via the `SOCIAL_DB`
env var — no shared state, no repo pollution. Seed: two users (`alice`, `bob`),
one post (`post_id=1`), one comment (`post_id=1, author_id=alice, content='hello'`).

## A. Acceptance 1 — schema creation

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Empty DB; `db.init_db()` | `comment_likes` table exists in `sqlite_master` |
| A2 | Inspect table DDL | `UNIQUE(user_id, comment_id)` is enforced (duplicate raw INSERT raises `IntegrityError`) |
| A3 | Legacy tables after adding `comment_likes` | `users`, `posts`, `comments`, `likes` still present |

## B. Acceptance 1 — duplicate like idempotence

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Bob not liking comment; `add_comment_like(bob, c)` | Returns `True`; exactly one `(bob,c)` row |
| B2 | `(bob,c)` present; `add_comment_like(bob, c)` again | Returns `False`; still exactly one row; no exception |
| B3 | Alice and Bob both like the comment | Two rows, one per user |

## C. Acceptance 4 — remove idempotence

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `(bob,c)` present; `remove_comment_like(bob, c)` | Returns `True`; `count_comment_likes(c) == 0`; row removed |
| C2 | `(bob,c)` absent; `remove_comment_like(bob, c)` again | Returns `False`; no exception |
| C3 | Removing Bob's like does not affect Alice's like | Only `(bob,c)` removed |

## D. Acceptance 5 — count

| # | Scenario | Expected |
|---|----------|----------|
| D1 | No likes; `count_comment_likes(c)` | `0` |
| D2 | One like added | `1` |
| D3 | Two users like; one removes | Counts `2` then `1` |
| D4 | Count is per comment | Likes on another comment are not counted |

## E. Acceptance 3 — foreign keys

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `add_comment_like(999, c)` | Raises `sqlite3.IntegrityError` |
| E2 | `add_comment_like(bob, 999)` | Raises `sqlite3.IntegrityError` |

## F. Acceptance 2 — existing `likes` table untouched

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Snapshot `likes` DDL + rows before/after `init_db()` and a `comment_likes` write | DDL identical, row count identical, no `comment_likes` rows leak into `likes` |

## G. Edge cases

| # | Scenario | Expected |
|---|----------|----------|
| G1 | Return types are plain `bool` | `is True` / `is False` |
| G2 | `is_comment_liked` true/false transitions | `False` → `True` → `False` |
| G3 | Persistence across reopen: `init_db()` again after a like | Like still present; row count stable |
| G4 | Comment-like and post-like counters are independent | A post like does not change `count_comment_likes` |

Skeleton/test file: `tests/test_fp001_comment_like_storage.py`.
