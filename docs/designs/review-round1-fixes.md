# Design: Review Round 1 Fixes (primes)

## Context
The round-1 verdict JSON from review task `task-mt17vsshrc` was not present in the
review artifacts and the PR (`guannanwlj/happygame#1`) carries no recorded review
comments, so the findings below were re-derived by re-reviewing the PR diff
(`task/task-mt15k682`: `primes.py`, `tests/test_primes.py`, docs) directly.

## Findings addressed

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| F1 | medium | `main()` lets `int(argv[1])` raise a raw `ValueError` traceback on non-integer input (e.g. `python primes.py abc`). | Catch conversion errors, print a friendly message to stderr, exit with code 2 (usage error). |
| F2 | medium | Extra CLI arguments are silently ignored (`python primes.py 100 200` runs with 100). | Treat more than one positional argument as a usage error with the same friendly handling. |
| F3 | medium | No test coverage for the CLI path: default limit, explicit limit, invalid input, extra args, exit codes, streams. | New `tests/test_cli.py` covering all of these (TDD). |
| F4 | low | `main()` lacked a docstring; the `math.isqrt(limit - 1)` bound was subtle and uncommented. | Add docstrings and a one-line comment explaining the sieve bound (largest candidate is `limit - 1`). |
| F5 | low | README had no usage documentation for the new CLI. | Add a short Usage section. |

## Key decisions
- Keep the manual `argv` parsing instead of pulling in `argparse`: the CLI surface is a
  single optional integer, and staying stdlib-trivial keeps the module dependency-free.
- Exit code 2 (not 1) for usage errors, matching the widespread CLI convention that
  `2` = bad usage; errors go to stderr, primes go to stdout.
- `main(argv)` keeps taking an explicit argv parameter (testable without monkeypatching
  `sys.argv`) and returns the process exit code so tests can assert it without `SystemExit`.
- Library semantics of `primes_below` are unchanged (already correct and well tested);
  this round only hardens the CLI wrapper and docs.

## Files
- `primes.py` — CLI hardening + docstrings/comments.
- `tests/test_cli.py` — new CLI tests.
- `README.md` — usage docs.
- `docs/test-cases/primes-cli.md` — test scenario documentation.
