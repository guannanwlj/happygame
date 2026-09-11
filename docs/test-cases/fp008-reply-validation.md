# FP-008 Test Scenarios — Reply Level and Content Validation

Module under test: `social_app/reply_service.py` (spec: task card FP-008
§3.2/§4/§7/§8). Every test runs against a fresh temporary DB file via the
`SOCIAL_DB` env var, initialized with the full schema and seeded with users
`alice`/`bob`, post `p1(alice)`, top-level comment `c1(post=p1, author=alice)`
and reply `c2(post=p1, author=bob, parent_id=c1)`.

## A. Happy path — reply to a top-level comment

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `add_reply(c1, bob, "hi")` | Returns an `int` id > 0 |
| A2 | Row for A1's id | `post_id == p1`, `parent_id == c1`, `author_id == bob`, content `"hi"` |
| A3 | Padded content `"  hi  "` | Accepted (non-blank after strip) and stored verbatim |
| A4 | `add_reply` delegates the write to storage | `comments.add_comment` called once with `(p1, bob, content)` and `parent_id=c1` |
| A5 | Two replies to `c1` | Both persisted, second id greater than first |

## B. Reply to a reply — rejected, no write

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `add_reply(c2, bob, "nested")` | Raises `ReplyError("只能回复顶层评论")`; `comments` row count unchanged |
| B2 | Same, after a successful reply exists | New row count stays at the pre-call value |
| B3 | Reject path with storage `add_comment` spied on | Storage write never called |

## C. Missing parent — rejected, no write

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `add_reply(999, bob, "hi")` | Raises `ReplyError("回复对象不存在")`; no new row |
| C2 | Missing parent with blank content | Parent-existence rule wins (`"回复对象不存在"`) — validation order §4 |
| C3 | Reject path with storage `add_comment` spied on | Storage write never called |

## D. Blank content — rejected, no write

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `add_reply(c1, bob, "   ")` | Raises `ReplyError("回复内容不能为空")`; no new row |
| D2 | `""`, `"\n\t"`, `" \n\t "` | Same as D1 |
| D3 | Blank attempt after a real reply | Real reply survives; row count stays at the pre-call value |

## E. Self-reply and exception contract

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `add_reply(c1, alice, "mine")` (alice authored `c1`) | Allowed; row written with `author_id == alice` |
| E2 | `ReplyError` is an `Exception` subclass | Catchable as `Exception` |
| E3 | `str(ReplyError(msg))` | Readable Chinese reason preserved |

## F. Storage mock (dependency isolation)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `reply_service.comments` replaced by an in-memory fake | Valid reply writes to the fake and returns its id |
| F2 | Fake with a reply-to-reply parent | `ReplyError` raised; fake stays empty |

Skeleton/test file: `tests/test_fp008_reply_validation.py`.
