# FP-001 Design: Mutual-Follow Check Primitive

Task card: `input/tasks/comment-visibility-mutual-friends/FP-001-mutual-follow-check.task.md`
(sole spec). Goal: deliver a pure read-only boolean primitive
`is_mutual_follow(a_id, b_id) -> bool` in a new module
`social_app/mutual_follows.py`, deciding in real time whether two users follow
each other. This is the dispatch data basis for the friend-post comment
visibility filtering (downstream FP-002 / FP-003). No existing page or route
behavior changes.

## Approach

- **New module, no schema work.** The `follows` table already exists in
  `social_app/db.py` (`SCHEMA_SQL`, card §3.1). The task is read-only: no new
  tables, columns, indexes, routes, or pages; nothing is written, cached, or
  snapshotted.
- **Derivation by directional reuse.** The card states the semantics as
  `is_following(a, b) and is_following(b, a)` and allows either two
  `query_one` round trips or one double-EXISTS SQL. We reuse the existing,
  already-tested primitive `social_app.follows.is_following` for both
  directions — least code, no duplicated SQL, and each check keeps the
  existing one-connection-per-call semantics (honoring `SOCIAL_DB` at call
  time, which is exactly what "real-time, no snapshot" requires).
- **Legacy `friendships` untouched.** The module never reads or writes the
  legacy request+confirm friend tables; the decision is based solely on
  `follows` rows.
- **Real-time semantics.** Because every call re-queries the current
  `follows` data, relationship changes (e.g. a row deleted to simulate
  unfollow) are reflected by the very next call — no invalidation logic
  needed.

## Key decisions

1. **Reuse `is_following` instead of a double-EXISTS query**: the card's
   equivalence statement becomes the implementation verbatim; single source
   of truth for the directional lookup SQL; short-circuit `and` skips the
   second query when the first direction is absent.
2. **Bool return from `is None` checks** stays in `follows.is_following`;
   `is_mutual_follow` adds no conversion of its own.
3. **Self-pair (`a_id == b_id`) is undefined upstream** (card §7 boundary
   note): no special guard is added; with normal data (no self-follow rows)
   the two directional checks both fail and the result is `False`. This
   behavior is not part of the promised contract.
4. **No `__init__.py` re-export**: consumers import
   `social_app.mutual_follows` directly per the card contract, keeping the
   package surface stable for concurrent wave-1 tasks (same decision as
   FP-004 follows storage).

## Verification

`python3 -m pytest -q tests/test_mutual_follows.py` (plus full-suite
regression `python3 -m pytest -q`). Scenarios documented in
`docs/test-cases/fp001-mutual-follow-check.md`. Seeding per card §6: temp DB
via `SOCIAL_DB` → `db.init_db()` → direct user inserts → `add_follow` /
`DELETE FROM follows` to build and mutate the three relation classes.
