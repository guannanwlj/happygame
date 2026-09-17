# FP-002 Test Scenarios — Mutual Friend Circle Computation

Module under test: `social_app/mutual_friends.py` —
`mutual_friend_ids(reader_id, author_id) -> set[int]` (spec: task card
FP-002 §1/§4/§7/§8). Every test uses a fresh temporary DB via the `SOCIAL_DB`
env var + `db.init_db()`; users are inserted directly, follow graphs built
with `follows.add_follow`, unfollows simulated with `DELETE FROM follows`
(card §6).

## A. Acceptance 1 — mutual friend included

| # | Scenario | Expected |
|---|----------|----------|
| A1 | M↔R and M↔P (four rows); `mutual_friend_ids(R, P)` | Set contains M |
| A2 | M and N both mutual with R and P | Set contains both M and N |

## B. Acceptance 2 — one-sided mutual excluded

| # | Scenario | Expected |
|---|----------|----------|
| B1 | S↔P only (S not mutual with R, may follow R one-way) | Set does not contain S |
| B2 | S→R and R→S missing variants (only one direction toward R) | Set does not contain S |

## C. Acceptance 3 — no common mutuals → empty set

| # | Scenario | Expected |
|---|----------|----------|
| C1 | R↔P mutual but nobody else is mutual with both | `mutual_friend_ids(R, P) == set()` |

## D. Acceptance 4 — R/P mutual-follow status irrelevant

| # | Scenario | Expected |
|---|----------|----------|
| D1 | R and P NOT mutual, M↔R and M↔P | Set still contains M |

## E. Acceptance 5 — real-time recalculation after unfollow

| # | Scenario | Expected |
|---|----------|----------|
| E1 | M↔R, M↔P; `DELETE FROM follows` removes M→R; recompute | Set no longer contains M |

## F. Edge cases / error handling

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Result type | `set` instance; elements are plain `int`s |
| F2 | Neither R nor P follows anyone / no follows rows at all | Empty set, no error |
| F3 | Unknown user ids (no such users) | Empty set, no error (pure read) |
| F4 | R == P | Users mutual with them are mutual "friends of both"; no self id leaks into the set |
| F5 | Idempotent recomputation: two consecutive calls | Identical sets (no caching side effects) |
| F6 | Legacy `friendships` rows present | Do not influence the result (not read) |

Skeleton/test file: `tests/test_mutual_friends.py`.
