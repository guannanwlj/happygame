# FP-023 Design: Feed Query Module

Task card: `input/tasks/social-like-comment/FP-023-feed-query.task.md` (sole
spec). Goal: add the missing `social_app/feed.py` with `get_feed(user_id)` so
the existing home feed (`social_app/views_feed.py`) can render real posts. The
module reads the existing `posts` / `follows` / `users` tables plus the
FP-015 `likes` and FP-016 `comments` tables, aggregating the like count,
the current user's like state, and the comment list per post.

## Approach

- **One new module `social_app/feed.py`**, mirroring the storage style of
  `social_app/follows.py` / `social_app/likes.py`: delegate all access to the
  generic API `social_app.db.query_all` / `query_one`; never open a raw
  connection here.
- **Author set** = `follows.list_followees(user_id) + [user_id]`, per card
  §4.1. Self is always included; an empty follow list still yields the user's
  own posts.
- **Post query** (`posts JOIN users` for the username) filters with an
  `IN (?, ?, ...)` placeholder list and orders `created_at DESC, id DESC`, so
  ties on the timestamp fall back to newest inserted first (card §3.2/§7).
  Because the literal SQL text varies with the number of authors, the `IN`
  list is built from placeholders and passed as bound parameters.
- **Per-post aggregation** uses the card's simple per-post queries (card §4,
  Q-001 implementation detail): `like_count` via `COUNT(*)`, `liked_by_me`
  via `SELECT 1 ... LIMIT 1`, and `comments` via `comments JOIN users`
  ordered `created_at ASC, id ASC`. This matches the specified keys and avoids
  a complex single join.
- **Return contract** (card §3.2): a `list[dict]` where each row has
  `post_id`, `author_id`, `username`, `content`, `created_at`, `like_count`,
  `liked_by_me`, and `comments` (each comment `{author, content, created_at}`).
- **Empty result** returns `[]` without raising: the author set always
  contains `user_id`, and a no-row `IN` query simply yields nothing.

## Key decisions

1. **Reuse the generic `db` API** so the `SOCIAL_DB` env override and
   connection-per-call semantics are honored automatically, consistent with
   FP-015/FP-024.
2. **Per-post queries, not one mega-join.** The card explicitly selects the
   simple aggregation strategy for the local small-scale case; it keeps each
   aggregate independently testable and readable.
3. **No `likes`/`comments` DDL here.** Those tables belong to FP-015/FP-016
   (card §5). FP-016 is not yet in the tree, so the FP-023 tests create the
   `likes`/`comments` tables from the card §3.1 DDL in the temp DB before
   seeding — proving the module is independently verifiable (card §6/§8).
4. **No new exports in `social_app/__init__.py`.** `views_feed` already
   imports `from social_app.feed import get_feed`; that lazy contract is
   satisfied by the module name alone.
5. **Read-only.** Posting, likes/comments writes, HTML rendering, and
   pagination are out of scope (card §5).

## Verification

`python3 -m pytest tests/test_fp023_feed_query.py -q` (plus the full suite,
baseline 380 passed). Scenarios documented in
`docs/test-cases/fp023-feed-query.md`.
