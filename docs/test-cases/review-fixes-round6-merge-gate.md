# Test Cases: Review Fixes Round 6 — Merge-Gate Recovery

Regression locks for the round-5 FAIL verdict (task-mt184d0qit, P0
`GATE:mergeable=UNKNOWN`).

## Scenarios

### 1. HEAD descends from `origin/main` (`test_head_descends_from_origin_main`)
- **Scenario**: `git merge-base --is-ancestor origin/main HEAD`.
- **Expect**: exit code 0 — the branch is rebased on top of the base, never diverged.
- **Covers**: the P0 gate finding in executable form; a branch left behind by an
  advancing `main` (the classic road to CONFLICTING/UNKNOWN gates) turns red locally.
- **Skip path**: when `origin/main` is not a local ref (shallow CI checkout of a PR
  merge ref), the scenario cannot be evaluated → `pytest.skip`.
- **Error path**: non-zero git exit fails the test with stderr attached.

### 2. Branch merges cleanly into `origin/main` (`test_branch_merges_cleanly_into_origin_main`)
- **Scenario**: pre-existing round-3 lock, re-run at the round-6 tip.
- **Expect**: `git merge-tree --write-tree origin/main HEAD` exits 0.

### 3. Full suite stays green
- **Scenario**: `python -m pytest -q` and bare `pytest` from the repo root.
- **Expect**: all tests pass (29 pre-existing + 1 new lock).

## Verification performed outside the unit suite
- `git fetch origin main` then `git rebase origin main` — "Current branch
  task/task-mt17w2mbkp is up to date" (no conflicts; `--continue` not needed).
- `git merge-base --is-ancestor origin/main HEAD` → 0; `git merge-tree --write-tree
  origin/main HEAD` → 0.
- `git push --force-with-lease origin HEAD` recreates `origin/task/task-mt17w2mbkp`
  (the ref was deleted on PR merge, the root cause of UNKNOWN); the restored head gives
  GitHub a merge ref to build `ci.yml` against.
