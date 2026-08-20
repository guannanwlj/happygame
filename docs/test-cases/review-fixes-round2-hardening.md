# Test Cases: Review Fixes Round 2 — Hardening

Extends `review-fixes-round2.md` for the round-2 hardening (root conftest + CI shape lock).

## Scenarios
1. **Root conftest present**: `conftest.py` exists at the repo root — the file that makes
   `from primes import ...` resolvable via pytest's prepend import mode.
2. **Bare `pytest` from repo root** (regression, unchanged): collecting `tests/test_primes.py`
   with the bare executable succeeds, no `ModuleNotFoundError`.
3. **`python -m pytest`** (regression, unchanged): collection via the module form succeeds.
4. **Import independent of the `pythonpath` ini**: bare `pytest` with the ini neutralized
   (`-o pythonpath=`) still collects cleanly — proves the root conftest carries the import
   on its own (defense-in-depth).
5. **CI workflow shape**: `.github/workflows/ci.yml` exists, triggers on `push` and
   `pull_request`, checks out the code (`actions/checkout`), sets up Python
   (`actions/setup-python`), and runs pytest.

## Edge cases
6. **Bare `pytest` not on PATH**: the bare-executable test skips (not fail) so the suite
   stays portable; the ini-independence test falls back to `python -m pytest` so the
   defense-in-depth check always runs.

## Error handling
7. **Subprocess failure**: non-zero exit or `ModuleNotFoundError` in output fails the test;
   stdout/stderr are surfaced in the assertion message for diagnosis.
8. **Workflow missing/misconfigured**: any missing trigger or step fails the workflow test
   with a message naming the expectation.

## Out of scope
- The primes unit tests themselves (unchanged; see `primes.md`).
