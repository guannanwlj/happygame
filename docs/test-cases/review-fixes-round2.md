# Test Cases: Review Fixes (Round 2)

Covers the tooling fixes for the round-1 findings: bare `pytest` discoverability and CI setup.

## Scenarios
1. **Bare `pytest` from repo root**: collecting `tests/test_primes.py` with the bare `pytest`
   executable succeeds (exit code 0, no `ModuleNotFoundError: No module named 'primes'`).
2. **`python -m pytest` regression guard**: collecting via `python -m pytest` still succeeds.

## Edge cases
3. **Bare `pytest` not on PATH**: the subprocess test is skipped (not failed) so the suite stays
   portable to environments without the console script.

## Error handling
4. **Subprocess failure**: a non-zero exit code (e.g. collection error) fails the test and the
   subprocess stdout/stderr is surfaced in the assertion message for diagnosis.
5. **CI workflow missing/misconfigured**: `.github/workflows/ci.yml` must exist, trigger on both
   `push` and `pull_request`, and run pytest in a step — otherwise the test fails.

## Out of scope
- The primes unit tests themselves (unchanged; see `primes.md`).
