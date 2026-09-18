# Design: Review Fixes Round 6 — Merge-Gate Recovery

## Goal
Resolve the round-5 FAIL verdict (task-mt184d0qit) whose sole finding is the P0 merge
gate: `GATE:mergeable=UNKNOWN` — the PR's mergeability could not be evaluated and its
checks were not green.

## Root cause
PR #2 (head `task/task-mt17w2mbkp`) and PR #3 (head `task/task-mt15k682`) were both
merged and their head branches deleted on merge. With the head ref gone, GitHub cannot
report a mergeability state for the review's PR at all — hence UNKNOWN rather than
MERGEABLE/CONFLICTING — and no checks run against a missing head. The branch content
itself was already fully absorbed into `origin/main` (branch tip `ebc4f59` is
byte-identical to `origin/main`), so there was no code defect to fix.

## Approach
1. `git fetch origin main` — refresh the base (done; `origin/main` = `ebc4f59`).
2. `git rebase origin main` — no-op: `HEAD` is already `origin/main`, so the rebase
   applies zero commits and reports the branch up to date. There is no conflict to
   resolve and `git rebase --continue` is never needed.
3. Make the branch publishable again: add this round's commit (docs + one regression
   lock) so the head ref has content beyond `main` for GitHub to evaluate, then
   `git push --force-with-lease origin HEAD` to recreate `refs/heads/task/task-mt17w2mbkp`.
   The lease is vacuously satisfied because the remote ref does not exist.
4. With the head restored, `merge-tree --write-tree origin/main HEAD` is trivially clean
   (the branch is a strict descendant of `main`) and `ci.yml` — whose `pull_request:`
   trigger is unfiltered — has a head to build, so checks can go green.

## Key decisions
- **No code changes to `primes.py`/`tests` semantics**: the finding is purely a repo-state
  defect; the 29-test suite was green at the branch tip before and stays green.
- **Executable lock (`tests/test_repo_hygiene.py`)**: `test_head_descends_from_origin_main`
  asserts `git merge-base --is-ancestor origin/main HEAD`, i.e. the branch must never
  diverge from the base. This is the executable form of "rebase before pushing" and turns
  any future gate regression (stale branch after main advances) into a red test locally
  instead of an UNKNOWN gate at review time. It skips under the same shallow-checkout
  condition as the existing merge-cleanliness lock.
- **Docs-only payload plus one test**: matches the per-round convention of
  `docs/designs/*` + `docs/test-cases/*` notes with the regression lock that each
  merge-state round has added.

## Files
- `tests/test_repo_hygiene.py` — new `test_head_descends_from_origin_main` lock
- `docs/designs/review-fixes-round6-merge-gate.md`,
  `docs/test-cases/review-fixes-round6-merge-gate.md` — this round's docs
