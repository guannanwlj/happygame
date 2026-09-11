# FP-017 Test Scenarios — Like Service

Module under test: `social_app/like_service.py` (spec: task card FP-017
§4/§7/§8). Every test uses a fresh temporary DB file via the `SOCIAL_DB` env
var; FP-015 is merged, so the real `social_app/likes.py` storage backs the
service. Seed: two users and one post.

## A. Acceptance 1 — like increments total

| # | Scenario | Expected |
|---|----------|----------|
| A1 | No likes; `like(A, P)` | Returns `1`; one `(A, P)` row |
| A2 | A already likes P; `like(B, P)` | Returns `2` (per-post total) |

## B. Acceptance 2 — like is idempotent

| # | Scenario | Expected |
|---|----------|----------|
| B1 | A likes P twice | Second call still returns `1`; one row; no exception |
| B2 | A and B like P; `like(A, P)` again | Returns `2` (unchanged) |

## C. Acceptance 3 — unlike decrements and is idempotent

| # | Scenario | Expected |
|---|----------|----------|
| C1 | A likes P; `unlike(A, P)` | Returns `0`; row removed |
| C2 | A and B like P; `unlike(A, P)` | Returns `1`; only B's row remains |
| C3 | A does not like P; `unlike(A, P)` | Returns `0`; no exception |

## D. Acceptance 4 — count_likes

| # | Scenario | Expected |
|---|----------|----------|
| D1 | No likes on P | `count_likes(P)` returns `0` |
| D2 | A and B like P | Returns `2` |
| D3 | Count is per-post: P like does not affect Q | `count_likes(Q)` stays `0` |

## E. Isolation / edge cases

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Storage absent: monkeypatch `add_like`/`remove_like`/`count_likes` with in-memory fakes; `like(A, P)` twice then `unlike(A, P)` | `1, 1, 0`; proves the service is verifiable without FP-015 |
| E2 | Return types | All three functions return `int` |

Skeleton/test file: `tests/test_fp017_like_service.py`.
