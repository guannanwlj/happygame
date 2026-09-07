# FP-011 Test Cases: Friends-Feed Timeline

Module under test: `social_app/feed.py` (`GET /feed`) with the self-built
FP-003 contract stub (`social_app/auth.py`) and minimal app shell
(`social_app/app.py`). Test file: `tests/test_fp011_feed.py`.

Setup common to all scenarios (task card §6 seed, via a fresh `$SOCIAL_DB`
tmp file + `db.init_db`):

- Users `alice` / `bob` / `carol` / `dave`.
- Friendships (bidirectional two-row pairs, FP-008 mock): alice–bob,
  alice–carol. dave is friends with nobody.
- Posts (FP-010 mock, explicit `created_at` so ordering is deterministic):
  - bob: 「bob-old」 @ `2026-09-01T10:00:00.000Z`,
    「bob-new」 @ `2026-09-03T09:00:00.000Z` (deliberately straddling carol)
  - carol: 「carol-mid」 @ `2026-09-02T12:00:00.000Z`
  - dave: 「dave-solo」 (non-friend → must not appear)
  - alice: 「alice-own」 (own post → must not appear)
- Login state injected through `client.session_transaction()` (FP-003 mock).

## A1 — Friends' posts fully visible, newest first (acceptance 1)

Given the seed, When logged-in alice opens `/feed`, Then the response is
200 and contains all three friend posts (bob-old, bob-new, carol-mid) in
exactly the order bob-new → carol-mid → bob-old (publish time DESC). Each
rendered entry contains the author's username, the publish timestamp and
the content.

## A2 — Non-friend and own posts excluded (acceptance 2)

Given the seed, When logged-in alice opens `/feed`, Then 「dave-solo」 and
「alice-own」 do not appear anywhere in the response.

## A3a — Empty state: no friends at all (acceptance 3)

Given dave has no friendships, When logged-in dave opens `/feed`, Then the
page shows the empty state 「暂无好友动态」 and none of the seeded posts.

## A3b — Empty state: friends exist but never posted (acceptance 3 variant)

Given user `erin` is friends with `frank` and frank has no posts, When
logged-in erin opens `/feed`, Then the empty state is shown (200, not an
error).

## A4 — Anonymous access redirected to login (acceptance 4)

Given no login state in the session, When `/feed` is requested, Then the
response is 302 with `Location: /login` (FP-003 `login_required` contract).

## E1 — DB-level query isolation (edge)

The §3.1 contract query run directly returns exactly the three friend rows
for alice in DESC order — guards the feed against drift between route and
contract (e.g. own/non-friend rows leaking in through later refactors).

## E2 — Template shell wiring (edge)

`feed.html` extends `base.html` and overrides the title block; the rendered
page carries the 「好友动态」 title (guards the FP-002 inheritance contract).
