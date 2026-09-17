# FP-001 Test Scenarios — Mutual-Follow Check Primitive

Module under test: `social_app/mutual_follows.py` (`is_mutual_follow`,
spec: task card FP-001 §4/§6/§7/§8). Every test uses a fresh temporary DB
file via the `SOCIAL_DB` env var + `db.init_db()` (convention of
`tests/test_fp023_feed_query.py`); users are inserted directly, follows are
seeded through the existing `add_follow`, and "unfollow" is simulated with a
direct `DELETE FROM follows` (card §6).

## A. Acceptance 1 — mutual pair

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Seeds A→B and B→A rows; `is_mutual_follow(A, B)` | `True` |
| A2 | Symmetry: same seeds, `is_mutual_follow(B, A)` | `True` |

## B. Acceptance 2 — one-way pair

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Seeds only A→B; `is_mutual_follow(A, B)` | `False` |
| B2 | Same seeds, reversed argument order `is_mutual_follow(B, A)` | `False` |

## C. Acceptance 3 — no relationship

| # | Scenario | Expected |
|---|----------|----------|
| C1 | A and B seeded, no follows rows between them | `False` |
| C2 | Unrelated third user C vs. A | `False` |

## D. Acceptance 4 — real-time follow deletion (no snapshot)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | A↔B mutual, then `DELETE FROM follows` removes B→A; call again | `False` |
| D2 | D1 then re-`add_follow(B, A)`; call again | `True` (semantics follow current data both ways) |

## E. Edge cases / boundaries

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Legacy isolation: `friendships` rows (A,B)+(B,A) inserted, no `follows` rows | `False` — decision never reads the legacy table |
| E2 | Self-pair `is_mutual_follow(A, A)` with no self-follow rows | `False` (boundary note only, not a promised semantics — card §7) |
| E3 | Return type is a plain `bool` (`is True` / `is False`) | holds for both outcomes |
| E4 | Module does not mutate data: `follows` row set unchanged after a call | unchanged |

Skeleton/test file: `tests/test_mutual_follows.py`.
