# FP-006 Test Scenarios — Comment Like Service

Module under test: `social_app/comment_like_service.py` (spec: task card FP-006
§4/§7/§8). Every test uses a fresh temporary DB file via the `SOCIAL_DB` env
var; FP-001 is merged, so the real `social_app/comment_likes.py` storage backs
the service. Seed: users `alice` and `bob`, post `p1(alice)`, comment
`c1(post=p1, author=alice)`.

## A. Acceptance 1 — like increments total & is idempotent

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `c1` 0 likes; `like_comment(bob, c1)` | Returns `1`; one `(bob, c1)` row |
| A2 | Bob already likes c1; `like_comment(bob, c1)` | Still returns `1`; still one row; no exception |

## B. Acceptance 2 — unlike decrements & is idempotent

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Bob likes c1; `unlike_comment(bob, c1)` | Returns `0`; row removed |
| B2 | Bob already unliked; `unlike_comment(bob, c1)` again | Still returns `0`; no exception |
| B3 | Bob never liked c1; `unlike_comment(bob, c1)` | Returns `0`; no exception |

## C. Acceptance 3 — self-like allowed (D6)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Author `alice` likes her own comment `c1` | Returns `1`; no restriction |

## D. Acceptance 4 — independent per-comment counts

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Two different users like c1 | `count_comment_likes(c1) == 2`; remove one → `1` |
| D2 | Count is per-comment: like on c2 does not affect c1 | `count_comment_likes(c1) == 0`, `count_comment_likes(c2) == 1` |

## E. Acceptance 5 — independent from post likes (D8)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Post like and comment like each exist | Post count unaffected by comment like; comment count unaffected by post like |

## F. Isolation / edge cases

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Storage absent: monkeypatch `add_comment_like`/`remove_comment_like`/`count_comment_likes` with in-memory fakes; `like_comment` twice then `unlike_comment` | `1, 1, 0`; proves the service is verifiable without FP-001 |
| F2 | Return types | All three functions return `int` |
| F3 | `count_comment_likes` transparent through the service | Reflected after like/unlike |

Skeleton/test file: `tests/test_fp006_comment_like_service.py`.
