# Design: Review Fixes Round 2 — Hardening

## Goal
Resolve the two findings that survived the round-2 review (task-mt184d0qit, re-asserting
the round-1 findings from task-mt17vsshrc):

1. **Bare `pytest` robustness**: `pytest.ini` sets `pythonpath = .`, which fixes the
   `ModuleNotFoundError: No module named 'primes'` for bare `pytest`. But the reviewer
   recommended defense-in-depth ("an empty conftest.py at repo root or a pyproject with
   pythonpath") because relying on a single mechanism leaves the import fragile.
2. **CI presence**: `.github/workflows/ci.yml` exists on this branch, but the reviewer
   observed zero checks on the reviewed PR. Lock the workflow's shape in with tests so
   regressions are caught locally.

## Approach

### Finding 1 — add a root `conftest.py`
- An empty `conftest.py` at the repo root makes pytest (prepend import mode, the default)
  insert the repo root at the front of `sys.path` when it loads the root conftest during
  collection. This is core pytest behavior, independent of the `pythonpath` ini option.
- Keep `pytest.ini` (`pythonpath = .`, `testpaths = tests`): the two mechanisms are
  complementary — the ini also pins rootdir and the default target; the conftest covers
  environments/overrides where the ini is absent or neutralized.
- Verified failure mode (current repo, before this change):
  `pytest -o pythonpath= --collect-only -q tests/test_primes.py` → collection error
  (`ModuleNotFoundError`). With the root conftest present it passes, proving the
  conftest alone carries the import.

### Finding 2 — pin the CI workflow shape with tests
- `ci.yml` (on `push` to main + all `pull_request` events) already runs
  `python -m pytest -q` on Python 3.12. Strengthen `tests/test_tooling.py` to assert the
  workflow uses `actions/checkout`, `actions/setup-python`, and runs pytest, so accidental
  removal/misconfiguration fails locally instead of silently producing zero checks.

## Key decisions
- Root `conftest.py` instead of `pyproject.toml`: the repo has no packaging metadata to
  migrate, and conftest works on every pytest version/import mode.
- New regression test neutralizes the ini with `-o pythonpath=` rather than copying the
  tree to a sandbox — it exercises the real repo from the real root with minimal moving parts.
- No changes to `primes.py` or the primes tests; this round is tooling-only.

## Files
- `conftest.py` — new, empty root conftest (import-path defense-in-depth)
- `tests/test_tooling.py` — new tests: conftest presence, ini-independent collection,
  stronger workflow assertions
