# FP-023 Test Scenarios — Feed Query Module

Module under test: `social_app/feed.py` (`get_feed`) against the existing
`users` / `posts` / `follows` tables plus the FP-015 `likes` and FP-016
`comments` tables (spec: task card FP-023 §3.1/§3.2/§4/§7/§8).

Every test uses a fresh temporary DB file via the `SOCIAL_DB` env var and calls
`db.init_db()`. FP-016 is not yet in the tree, so the `likes`/`comments` DDL
from card §3.1 is applied with `executescript` before seeding interaction data
(card §6 mock strategy) — no shared state, no repo pollution.

Seed fixture: users A (`alice`), B (`bob`), C (`carol`); A follows B; B posts
older content, A posts newer content, C posts content A must never see;
`likes` / `comments` rows are added per test.

## A. Acceptance 1 — self + followees, newest first

| # | Scenario | Expected |
|---|----------|----------|
| A1 | A follows B; B and A each posted at different times; `get_feed(A)` | Contains A's and B's posts only |
| A2 | Same call | Rows ordered `created_at DESC` with usernames resolved via `users` |
| A3 | C posted but A does not follow C | C's post is absent from the result |
| A4 | Two posts by A with the same `created_at` | Ordered `id DESC` (stable tie-break) |
| A5 | A follows B; `get_feed(B)` | B's feed contains only B's post, not A's |

## B. Acceptance 2 — like aggregation

| # | Scenario | Expected |
|---|----------|----------|
| B1 | B's post liked by A and C (two users) | `like_count == 2` |
| B2 | Same row, viewer A has liked it | `liked_by_me is True` |
| B3 | B's post also read by B (no B like) | `liked_by_me is False`; `like_count` unchanged |
| B4 | A's own post with no likes | `like_count == 0`, `liked_by_me is False` |

## C. Acceptance 2 — comments aggregation

| # | Scenario | Expected |
|---|----------|----------|
| C1 | B's post has two comments at different times | `comments` length 2, ordered `created_at ASC` |
| C2 | Comment rows | Each has `author` (username), `content`, `created_at` |
| C3 | Post with no comments | `comments == []` |
| C4 | Two comments with the same `created_at` | Ordered `id ASC` (tie-break) |

## D. Acceptance 3 — empty result

| # | Scenario | Expected |
|---|----------|----------|
| D1 | A exists, respects nothing, has no posts; `get_feed(A)` | `[]` |
| D2 | A follows a user who has no posts | `[]` |
| D3 | `get_feed` on an unknown user id | `[]`, no exception |

## E. Acceptance 4 — independent verification (card §6/§8)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Fresh DB with `likes`/`comments` dropped, then card §3.1 DDL applied | Both tables exist after `executescript` |
| E2 | After E1, seed a post + like + comment | `get_feed` aggregates correctly, proving the module is testable without upstream modules |
| E3 | Row contract | Keys are exactly `post_id`, `author_id`, `username`, `content`, `created_at`, `like_count`, `liked_by_me`, `comments`; types int/str/int/bool/list |

Skeleton/test file: `tests/test_fp023_feed_query.py`.
