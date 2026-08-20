# Design: Fix Review Findings (Round 2)

## Goal
Address the two non-blocking P3 findings from the round-1 review (task-mt17vsshrc):

1. Bare `pytest` from the repo root fails with `ModuleNotFoundError: No module named 'primes'`;
   only `python -m pytest` works. The design doc also over-claims the tests are "stdlib-runnable".
2. No CI pipeline: `.github/workflows` is missing, so nothing runs the test suite automatically.

## Approach

### Finding 1 — make bare `pytest` work
- Add a root `pytest.ini` with:
  - `pythonpath = .` — puts the repo root on `sys.path` so `from primes import ...` resolves
    (natively supported since pytest 6.1; this repo uses pytest 9.1.1).
  - `testpaths = tests` — makes a bare `pytest` invocation target the test directory.
- Chosen over an empty root `conftest.py` because it is explicit, also pins rootdir, and
  documents the intended default invocation.
- Fix `docs/designs/primes.md` wording: drop "stdlib-runnable" (tests import pytest).

### Finding 2 — add CI
- Add `.github/workflows/ci.yml`: on `push` and `pull_request`, checkout, set up Python 3.12,
  `pip install pytest`, run `python -m pytest -q`.

## Guard tests
- `tests/test_tooling.py` invokes bare `pytest` (and `python -m pytest`) as subprocesses from the
  repo root with `--collect-only` on `tests/test_primes.py` — collection is exactly where the
  round-1 failure occurred, and `--collect-only` avoids recursive suite execution.
  If no bare `pytest` executable is on PATH, the test skips (portability edge case).
- A workflow smoke test asserts the CI file exists, triggers on push/pull_request, and runs pytest.
  It uses textual assertions because PyYAML is not available in this environment.

## Key decisions
- `pytest.ini` + `pythonpath` instead of `conftest.py` (explicit, pins rootdir/testpaths).
- Subprocess tests use `--collect-only` to keep them fast and non-recursive.
- CI pins Python 3.12 to match local development; single job keeps it minimal.
