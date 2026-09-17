# FP-003 Test Scenarios — Friend-Post Comment Visibility Filter

Modules under test: `social_app/comment_visibility.py`
(`visible_comments(post_author_id, viewer_id, comments) -> list`) and its
wiring into the feed convergence point `social_app.feed._comments` /
`feed.get_feed` (spec: task card FP-003 §3.2/§4/§7/§8). Seeds follow card §6:
fresh temp DB via `SOCIAL_DB` + `db.init_db()`, users R/P/M/S/T inserted
directly, follow graphs via `follows.add_follow` (mutual / one-way / none),
comments inserted directly (incl. `parent_id` reply trees), unfollow via
`DELETE FROM follows`, failures via monkeypatched raisers.

Persons: R = reader, P = post author (friend when R↔P mutual), M = mutual
friend of R and P, S = stranger to R, T = one-way follower of R.

## A. Pure dispatch — own post / non-mutual post (card §7.7, §7.8, §7.11)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `viewer == post_author`, arbitrary comment authors | Same list returned unchanged (identity), no filtering |
| A2 | R and P not mutual (no rows), comments from anyone | Same list returned unchanged |
| A3 | R one-way follows P (P does not follow R) | Same list returned unchanged |
| A4 | Empty comments input, any dispatch branch | `[]` (unfiltered branch: same empty list) |

## B. Pure filter — mutual friend post (card §7.1–§7.5)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | R↔P mutual; M mutual with both; S unrelated; both commented P's post | Only M's rows kept; S's dropped; relative order preserved |
| B2 | P comments own post (top-level and reply) | P's rows kept (`{P}` in visible set) |
| B3 | R comments P's post | R's rows kept (`{R}` in visible set) |
| B4 | S top-level comment carrying replies from S and M | S's top-level and S's reply dropped; M's reply kept |
| B5 | S top-level comment carrying M's reply | S's top-level dropped; M's reply survives in the filtered list |
| B6 | All rows from non-visible authors | `[]` |
| B7 | Rows as `sqlite3.Row` and as `dict` | Both shapes filtered identically |
| B8 | Filter output order | Subset keeps the input's relative order exactly |

## C. Pure fail-closed (card §7.10)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `is_mutual_follow` raises (monkeypatch) | `[]` |
| C2 | `mutual_friend_ids` raises (monkeypatch) | `[]` |
| C3 | Row missing `author_id` key | `[]` (judgment failure prefers less) |
| C4 | Own-post branch (`viewer == post_author`) — decision cannot fail | Rows returned even though other primitives raise |

## D. Feed wiring — `feed.get_feed` (card §7.1–§7.9)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | R↔P mutual, M and S commented P's post | P's row `comments` contain M's only, S's absent, FP-009 dict shape and order kept |
| D2 | P's own comment and reply on P's post | Both present |
| D3 | R's own comment on P's post | Present |
| D4 | M top-level with S's reply and M's reply | S's reply hidden; both M rows kept |
| D5 | S top-level with M's reply | Filtered list drops S, keeps M; `_split_comments` promotes M's reply to top level |
| D6 | P's post where every comment is from non-visible authors | `comments == []` |
| D7 | R's own post commented by S, T, M | All three shown unfiltered (status quo) |
| D8 | R one-way follows P, S commented P's post | S's comment shown (status quo) |
| D9 | R↔P mutual then `DELETE FROM follows` removes P→R; R still follows P | P's post comments shown in full (real-time fallback) |
| D10 | Monkeypatched visibility primitive raises while R↔P mutual | That post's `comments == []` |
| D11 | Regression: non-friend / own posts keep exact FP-009 dict keys | Contract unchanged |

## E. End-to-end — `GET /` (card §7.1, §7.5, §7.6, §7.11)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Logged-in R, P's friend post with M and S comments | 200; M's comment rendered; S's content absent from body |
| E2 | S top-level hidden, M's reply survives | M's reply rendered at top level (promoted, `comment` class without `reply`) |
| E3 | Friend post whose comments are all filtered out | `comments-empty` 「暂无评论」 rendered for that post |
| E4 | Anonymous `GET /` | 303 redirect to `/login` (status quo; feed never queried) |

Test files: `tests/test_comment_visibility.py` (A–C),
`tests/test_feed_visibility.py` (D–E).
