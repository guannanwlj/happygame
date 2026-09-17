# FP-002 Design: Mutual Friend Circle Computation

Task card: `input/tasks/comment-visibility-mutual-friends/FP-002-mutual-friend-circle.task.md`
(sole spec). Goal: deliver a pure, real-time computation
`mutual_friend_ids(reader_id, author_id) -> set[int]` — the set of users who
are mutual follows of **both** the reader R and the author P — in a new module
`social_app/mutual_friends.py`. This is the "mutual friends" component of the
friend-post comment visibility set; the filtering itself is FP-003's job.

## Approach

- **New module, read-only.** `social_app/mutual_friends.py` exposes exactly one
  function. It reads the existing `follows` table through the generic access
  API (`db.query_all`), so the `SOCIAL_DB` env var is honored automatically.
  No writes, no cache, no new tables/columns/indexes, no route or page change.
- **Single-SQL set intersection.** A user `m` is a mutual friend of R and P
  iff four `follows` rows exist simultaneously: `m→R`, `R→m`, `m→P`, `P→m`.
  One query scans followers of R and verifies the other three directions with
  `EXISTS` subqueries — the direct translation of the card's equivalent SQL.
  `UNIQUE (follower_id, followee_id)` guarantees each `m` appears at most
  once, so the result needs no `DISTINCT`.
- **Real-time semantics, no snapshot.** Every call derives the answer from the
  current `follows` data; deleting a follow row (e.g. `DELETE FROM follows`)
  immediately affects the next call. Documented in the module docstring.
- **Deliberately no R/P check.** Whether R and P are mutual follows is
  irrelevant to the set computation — enabling the filter is the caller's
  (FP-003's) decision. Stated in the docstring and pinned by a test.
- **FP-001 isolation.** The card's weak dependency (`is_mutual_follow`) is not
  imported; the set-intersection implementation is self-contained per card §6,
  and semantic equivalence with the FP-001 path is checked at integration time.

## Key decisions

1. **One SQL statement over Python set algebra**: fewer round trips and the
   four-row condition is stated once, reviewable against the card verbatim.
2. **`set[int]` return built from `row["friend_id"]`**: plain `int`s (not
   `sqlite3.Row` wrappers), unordered — a set matches the contract.
3. **Unknown / follow-less user ids are not errors**: the query simply returns
   no rows → empty set. Pure read, nothing to validate here (authorization
   belongs to callers).
4. **No `__init__.py` re-export**: consumers import
   `social_app.mutual_friends` directly per the card contract; the package
   surface stays stable for concurrent wave-1 tasks.
5. **Legacy `friendships` untouched**: the request+confirm model is unrelated
   to this feature and is neither read nor written.

## Verification

`python3 -m pytest -q tests/test_mutual_friends.py`, then full-suite regression
`python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp002-mutual-friend-circle.md`.
