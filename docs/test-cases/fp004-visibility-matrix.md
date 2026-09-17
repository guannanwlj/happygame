# FP-004 Test Scenarios — Visibility Rules Test Matrix

Module under test: the whole visibility stack behind UC-001/UC-002/UC-003 —
`social_app.comment_visibility.visible_comments` (FP-003, matrix main object),
`social_app.feed.get_feed` (convergence point) and `GET /` rendering, plus the
decision primitives `social_app.mutual_follows.is_mutual_follow` (FP-001) and
`social_app.mutual_friends.mutual_friend_ids` (FP-002) at their real-time
boundaries (task card FP-004 §3.2/§4/§7/§8). Wave-3 start: FP-001/002/003 are
merged, so the matrix tests the real implementations (card §6, no shims).

Seeds follow card §6: fresh temp DB via `SOCIAL_DB` + `db.init_db()`, direct
inserts, unfollows via `DELETE FROM follows`, fail-closed via monkeypatched
raisers, login cookie via `session.create_session`.

## Personas (seed factory `world`)

| Key | Role | Follow edges |
|-----|------|--------------|
| R | reader/viewer | ↔P, ↔M, ↔M2, ↔N, →W |
| P | friend post author | ↔R, ↔M, ↔M2, ↔O |
| M, M2 | mutual friends of **both** R and P | ↔R, ↔P |
| N | mutual with R only (set boundary) | ↔R |
| O | mutual with P only (set boundary) | ↔P |
| S | stranger | none |
| T | one-way follower of R | →R |
| W | one-way followee of R (non-mutual author) | ←R |

Posts: `friend_post` (P), `own_post` (R), `oneway_post` (W) — all three land
in R's feed. `seeded_comments` adds a fixed comment tree on `friend_post`
(top-level rows from every persona + replies under a visible and a hidden
parent, deterministic created_at order).

## A. Visible-set matrix — friend post (UC-001, card §7.1)

Parametrized over the persona table: expected visible iff key ∈ {M, M2, P, R}.

| # | Scenario | Expected |
|---|----------|----------|
| A1–A4 | Top-level comment by M / M2 / P / R on `friend_post` | Shown in R's feed |
| A5–A9 | Top-level comment by N / O / S / T / W on `friend_post` | Hidden (N/O fail the mutual-with-**both** rule; S unconnected; T follows R one-way; W is followed by R one-way — no one-way shape enters the set) |
| A10 | Golden snapshot: full seeded tree, all personas at once | Exactly `m-top, m2-top, p-top, r-top, m-reply-under-s, r-reply-under-p` in `created_at ASC, id ASC` order; FP-009 dict keys per row |

## B. Dispatch contrast matrix (UC-002/UC-003, card §7.2)

Parametrized (post context × comment author):

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `friend_post` × M | Shown (filtered branch keeps visible set) |
| B2 | `friend_post` × S / T | Hidden |
| B3–B5 | `own_post` × S / T / M | All shown (status quo, no filtering) |
| B6–B8 | `oneway_post` × S / T / M | All shown (one-way follow ⇒ not mutual ⇒ status quo) |
| B9 | No-relationship pair, pure `visible_comments(S, R, rows)` | Same list object returned (identity, unfiltered) |
| B10 | Unfollow fallback: `DELETE P→R` (R still follows P) | `friend_post` comments revert to **full** (S's row appears); re-`add_follow(P, R)` filters again — both flips on the very next `get_feed` call |

## C. Nested-reply matrix (UC-001, card §7.1)

Parametrized (parent author × reply author), replies judged row by row:

| # | Parent | Reply | Parent shown | Reply shown | Shape |
|---|--------|-------|--------------|-------------|-------|
| C1 | M | M | yes | yes | reply nested under parent (`_split_comments` groups it) |
| C2 | M | R | yes | yes | nested |
| C3 | M | S | yes | **no** | reply-level hiding, parent unaffected |
| C4 | S | M | no | yes | **promoted to top level** (parent missing) |
| C5 | S | R | no | yes | promoted |
| C6 | S | S | no | no | `comments == []` |

## D. Empty state (card §7.1)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `friend_post` commented only by S and T | `comments == []` in feed; `GET /` renders `<p class="comments-empty">暂无评论</p>` |
| D2 | Post with zero comments (status quo) | Same empty-state rendering |
| D3 | Per-post isolation: same feed, friend post filtered empty, own post keeps its comment | Empty and non-empty states coexist |

## E. Fail-closed (card §7.1)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `is_mutual_follow` raises (monkeypatch) while reading R's feed | Friend post and one-way post comments `== []` (every post needing the mutual judgment fails closed); `own_post` keeps its full list (own-post branch short-circuits before the primitives) |
| E2 | `mutual_friend_ids` raises | `friend_post` comments `== []` |
| E3 | HTTP level: `mutual_friend_ids` raising, logged-in `GET /` | Friend post renders 暂无评论; own post and one-way post (dispatch never reaches the set computation) still render their comments |

## F. Primitive boundaries (FP-001/FP-002 weak-dep面, card §7.3)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `is_mutual_follow(P, R)` after `DELETE P→R` | `True → False` on the next call; re-add restores `True` |
| F2 | `is_mutual_follow(P, R)` after `DELETE R→P` | `False` (either direction breaks the mutual pair) |
| F3 | `mutual_friend_ids(R, P)` initial / after `DELETE M→P` / after re-add / after `DELETE R→M2` | `{M, M2} → {M2} → {M, M2} → {M}`; N and O never in the set |
| F4 | Composed: M leaves the circle (`DELETE M→P`), M's comment on `friend_post` | Hidden on the next `get_feed`; re-add → visible again (no snapshot in between) |

## G. End-to-end `GET /` (card §3.2 assertion surface)

| # | Scenario | Expected |
|---|----------|----------|
| G1 | Logged-in R, comments from every persona on `friend_post` | Visible contents in body; hidden contents absent |
| G2 | Hidden parent (S) + visible reply (M) | Reply rendered `<li class="comment">` at top level; no `<li class="comment reply">`, hidden parent's content absent |
| G3 | Visible parent (M) + hidden reply (S) + visible reply (M) | `<li class="comment reply">` present exactly for the visible reply; hidden reply absent |
| G4 | Friend post filtered to empty | `<p class="comments-empty">暂无评论</p>` (covered with D1) |
| G5 | Anonymous `GET /` | 303 redirect to `/login` |

Test file: `tests/test_visibility_matrix.py` (groups A–G).
