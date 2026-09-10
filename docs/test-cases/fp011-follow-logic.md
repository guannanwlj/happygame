# FP-011 Test Scenarios — Follow Rule Validation & Write

Module under test: `social_app/follow_service.py` (spec: task card FP-011
§3.3/§4/§7/§8). Every test runs against a fresh temporary DB file via the
`SOCIAL_DB` env var, seeded with users A (`alice`) and B (`bob`); `nobody` is
the non-existent target and `actor_id=None` models an anonymous caller.

## A. Happy path — one-directional write

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Users A, B seeded; `follow(A, "bob")` | `follows` contains `(A,B)`; no `(B,A)`; no exception |
| A2 | A follows B then C | Both `(A,B)` and `(A,C)` recorded, no reverse rows |
| A3 | `follow` returns `None` on success | Return value is `None` |

## B. Idempotence

| # | Scenario | Expected |
|---|----------|----------|
| B1 | A already follows B; `follow(A, "bob")` again | No exception; still exactly one `(A,B)` row |
| B2 | Repeat three times | Row count stays 1 |

## C. Rule violations — login / target / self

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `follow(None, "bob")` | Raises `FollowError("未登录")` |
| C2 | `follow(A, "nobody")` | Raises `FollowError("用户不存在")` |
| C3 | `follow(A, "alice")` (A targets self) | Raises `FollowError("不能关注自己")` |
| C4 | Anonymous caller with unknown target | `未登录` wins (first rule) |

## D. No side effects on rejection

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Self-follow rejected | `follows` table empty afterwards |
| D2 | Unknown target rejected | `follows` table empty afterwards |
| D3 | Anonymous rejected | `follows` table empty afterwards |

## E. Exception contract

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `FollowError` is an `Exception` | Catchable as `Exception`; `str(exc)` is the message |
| E2 | Empty / whitespace target username | Treated as non-existent → `FollowError("用户不存在")` |

## F. Write delegation (card §6)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `follow_service.add_follow` monkeypatched | Called exactly once with `(A, target_id)`; validated without storage |
| F2 | Invalid request with patched `add_follow` | Helper is never called (validation short-circuits) |

Skeleton/test file: `tests/test_fp011_follow_service.py`.
