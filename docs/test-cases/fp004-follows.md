# FP-004 Test Scenarios — Follow Relationship Storage

Modules under test: `social_app/follows.py` (helpers) and the `follows` table
added to `social_app/db.py` (spec: task card FP-004 §3.1/§3.3/§7/§8).
Every test uses a fresh temporary DB file via the `SOCIAL_DB` env var — no
shared state, no repo pollution.

## A. Acceptance 1 — one-directional insert

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Users A, B seeded; `add_follow(A, B)` | Returns `True`; `follows` gains `(A,B)` and no `(B,A)` opposite row |

## B. Acceptance 2 — idempotent re-follow

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `(A,B)` already present; call `add_follow(A, B)` again | Returns `False`; still exactly one `(A,B)` row; no exception |
| B2 | `add_follow` never leaks a duplicate-key error | `sqlite3.IntegrityError` not raised on repeat |

## C. Acceptance 3 — directional lookup

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `(A,B)` written; `is_following(A, B)` | `True` |
| C2 | `(A,B)` written; `is_following(B, A)` | `False` (directionality) |

## D. Acceptance 4 — list followees

| # | Scenario | Expected |
|---|----------|----------|
| D1 | A follows B then C; `list_followees(A)` | `[B, C]` (id list, insertion order) |
| D2 | User with no follows; `list_followees(D)` | `[]` |

## E. Acceptance 5 — persistence across reopen

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Write `(A,B)`, close all connections, reopen same file | Record still present; `is_following(A, B)` `True` after reopen |

## F. Acceptance 6 — foreign-key enforcement

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `add_follow(999, 1000)` with no such users | Raises `sqlite3.IntegrityError` (FK constraint) |

## G. Edge cases / error handling

| # | Scenario | Expected |
|---|----------|----------|
| G1 | `list_followees` returns plain `int`s | Elements are `int` instances |
| G2 | `is_following` returns plain `bool` | `is True` / `is False` |
| G3 | Schema idempotence: `init_db` twice | `follows` table still present, no error |
| G4 | Legacy friend tables remain intact | `friend_requests` / `friendships` still exist after adding `follows` |

Skeleton/test file: `tests/test_fp004_follows.py`.
