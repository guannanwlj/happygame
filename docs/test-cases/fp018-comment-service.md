# FP-018 Test Scenarios — Comment Service

Module under test: `social_app/comment_service.py` (spec: task card FP-018
§3.2/§4/§7/§8). Every test runs against a fresh temporary DB file via the
`SOCIAL_DB` env var, initialized with the full schema and seeded with a user
`alice` and a post `P`.

## A. Happy path — add and read back

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `add_comment(P, alice, "你好")` on an existing post | Returns an `int` id > 0; `list_comments(P)` contains the row with that content/author/post |
| A2 | Two comments on the same post | Both persisted, ids increase, list has 2 rows |
| A3 | Content with surrounding whitespace (`"  hi  "`) | Accepted (non-blank after strip) and stored verbatim |
| A4 | `add_comment` delegates the write to storage | `comments.add_comment` called once with `(P, alice, content)` |

## B. Blank content — rejected, no write

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `"   "` on a post | Raises `CommentError("评论内容不能为空")`; `comments` row count unchanged (0) |
| B2 | `"\n\t"` | Same as B1 |
| B3 | `""` | Same as B1 |
| B4 | `" \n\t "` mixed whitespace | Same as B1 |
| B5 | Blank attempt after one real comment | Real comment survives; row count stays 1 |
| B6 | Blank attempt with mocked storage | Storage `add_comment` never called |

## C. List — ascending order, scoping, empty

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Post with comments at 3 distinct `created_at` values (inserted out of order) | `list_comments(P)` returns them oldest-first |
| C2 | Same-millisecond rows sharing `created_at` | Tie-broken by ascending id |
| C3 | Two posts each with comments | `list_comments(P)` returns only P's comments |
| C4 | Post with no comments | Returns `[]` |
| C5 | `list_comments` delegates to storage | `comments.list_comments` called once with `P`, result passed through |

## D. Exception contract

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `CommentError` is an `Exception` subclass | Catchable as `Exception` |
| D2 | `str(CommentError("评论内容不能为空"))` | Readable Chinese reason |

## E. Storage mock (dependency absent / isolation)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `comment_service.comments` replaced by an in-memory fake | `add_comment` writes to the fake's list and returns its id; `list_comments` reads it back |
| E2 | Blank content with the fake installed | Fake's add never invoked; `CommentError` raised |

Skeleton/test file: `tests/test_fp018_comment_service.py`.
