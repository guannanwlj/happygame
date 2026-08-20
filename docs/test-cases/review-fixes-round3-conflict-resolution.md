# Test Cases: Review Fixes Round 3 — Merge-Conflict Resolution

Regression locks for the round-2 review FAIL verdict (task-mt18its6gv).
All live in `tests/test_repo_hygiene.py`.

## Scenarios

### 1. Tree tracks no bytecode artifacts (`test_tree_tracks_no_bytecode_artifacts`)
- **Scenario**: `git ls-files` over the checked-out tree.
- **Expect**: no path ends in `.pyc` and no path contains `__pycache__/`.
- **Covers**: P3 stray-artifact finding at the final-tree level.

### 2. History never adds bytecode artifacts (`test_history_never_adds_bytecode_artifacts`)
- **Scenario**: `git log --diff-filter=A --name-only HEAD --` filtered to pycache paths.
- **Expect**: no commit reachable from `HEAD` ever added a bytecode artifact.
- **Covers**: P3 at the history level (the `fd67915` failure mode); red before the
  history rewrite, green after.
- **Edge**: output is empty → assert empty list of offenders.

### 3. Branch merges cleanly into `origin/main` (`test_branch_merges_cleanly_into_origin_main`)
- **Scenario**: `git merge-tree --write-tree origin/main HEAD`.
- **Expect**: exit code 0 (clean merge); on conflict the test fails and prints the
  conflicted paths from stdout.
- **Covers**: P1 merge-conflict finding, executable form.
- **Skip path**: when `origin/main` is not a local ref (shallow CI checkout of a PR
  merge ref), the scenario cannot be evaluated → `pytest.skip`.
- **Error path**: non-zero git exit for reasons other than conflict fails the test with
  stderr attached.

## Error handling shared by all scenarios
- Every git invocation's exit code is checked (except the availability probe); stderr is
  included in failure messages for diagnosis.
- Tests require the `.git` directory (they no-op meaningfully only in a repo); in this
  repository that invariant always holds.

## Verification performed outside the unit suite
- Full suite green after the history rewrite (both `python -m pytest -q` and bare `pytest`
  with no arguments).
- `git merge-tree --write-tree origin/main HEAD` clean at the new tip.
- Force-push with `--force-with-lease` updates `origin/task/task-mt15k682`; the PR stops
  reporting CONFLICTING and CI checks can start (green confirmation is the reviewer's
  part per the P2 finding).
