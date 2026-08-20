# Design: Review Fixes Round 3 — Merge-Conflict Resolution

## Goal
Resolve the FAIL verdict from the round-2 review (task-mt18its6gv, reviewing PR #3):

1. **P1 (blocking)**: `task/task-mt15k682` CONFLICTS with `main`. Main advanced via the
   squash-merge of PR #1 (`b6cd99e`) carrying the same files this branch rebuilt from
   individual commits, so `git merge-tree --write-tree origin/main HEAD` reports add/add
   conflicts on `.github/workflows/ci.yml` and `tests/test_tooling.py` (and, during a
   commit-by-commit rebase, `docs/designs/primes.md` plus stray `tests/__pycache__/*.pyc`).
2. **P2 (blocking)**: zero CI checks on the PR — GitHub cannot build the merge ref while
   the PR is CONFLICTING, so `ci.yml` never starts. Resolving P1 and re-pushing unblocks
   the workflow; confirming the checks go green is the reviewer's/human's part.
3. **P3**: `tests/__pycache__/*.pyc` artifacts were committed in intermediate commit
   `fd67915` (later removed by `07294dd`). History hygiene that complicates the rebase.

The round-1 P3 findings (bare `pytest` import failure, missing CI) and the textual-CI-lock
P3 were already addressed on this branch by earlier rounds; that work is preserved as-is.

## Approach
The reviewer offered two equivalent paths: a commit-by-commit rebase with mechanical
conflict resolution, or one fresh commit on `origin/main` carrying only the main→branch
diff ("identical final tree, zero conflicts"). We take the fresh-commit path, split in two
for reviewability:

1. `git reset origin/main` (mixed reset) from `eea733a`: the working tree keeps the final
   branch content; only the commit pointer moves.
2. Commit A stages the pre-existing main→branch diff — `conftest.py`, the `pyyaml` line in
   `ci.yml`, the superset `tests/test_tooling.py`, and the round-2/round-3 docs. Final
   tree is byte-identical to the old branch tip.
3. Commit B adds this round's guards and docs (see below).

Because the branch now descends from `origin/main`, the merge is trivially clean, and the
`.pyc`-carrying intermediate commits (`fd67915`, `07294dd`) drop out of the branch history
entirely — main's squash commit never added them.

## Key decisions
- **Fresh commit over rebase**: deterministic (no multi-round conflict resolution), fixes
  the P3 history hygiene by construction, and produces the identical final tree the
  reviewer verified. History granularity from the fix rounds is already squash-summarized
  on main (`b6cd99e`), so nothing of value is lost.
- **Regression locks** (`tests/test_repo_hygiene.py`):
  - no `*.pyc` / `__pycache__` paths tracked in the tree;
  - no commit reachable from `HEAD` ever *added* bytecode artifacts (catches the
    `fd67915` failure mode resurfacing via future history edits);
  - `git merge-tree --write-tree origin/main HEAD` exits clean — the executable form of
    finding P1. Skips when `origin/main` is not a local ref (e.g. shallow `pull_request`
    checkouts in CI), where it cannot be evaluated.
- **Exit-code contract**: `git merge-tree --write-tree` exits 0 on a clean merge and 1 on
  conflict (git ≥ 2.38), so the test asserts on the exit code and prints the merged
  tree/conflict info on failure.
- **CI (P2)**: no workflow changes needed here — the conflict was the sole blocker.
  `ci.yml` keeps `pull_request:` unfiltered so checks appear on this PR once pushed.

## Files
- `tests/test_repo_hygiene.py` — new regression locks (tree hygiene, history hygiene,
  merge cleanliness vs `origin/main`)
- `docs/designs/review-fixes-round3-conflict-resolution.md`,
  `docs/test-cases/review-fixes-round3-conflict-resolution.md` — this round's docs
- Git history: branch rewritten as `origin/main` + commit A (carried diff) + commit B
