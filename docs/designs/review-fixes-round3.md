# Design: Review Fixes Round 3

## Goal
Address the verdict from task-mt17vsshrc (linked via trace_parent): PASS with two
non-blocking P3 findings, both `recommended_next_owner: dev_agent`:

1. Bare `pytest` from the repo root failed with `ModuleNotFoundError: No module named
   'primes'` (no root conftest / pytest.ini `pythonpath`).
2. No CI pipeline — `gh pr checks` reported zero checks.

Rounds 2 and the hardening round already fixed both (pytest.ini `pythonpath = .` +
`testpaths = tests`, root `conftest.py`, `.github/workflows/ci.yml`). This round
closes the residual gaps in those fixes found by re-auditing them against the
findings' literal scenarios.

## Gap analysis
- **Finding 1, literal scenario untested**: the round-2 tests always invoke pytest with
  an explicit path (`tests/test_primes.py`). The reviewer's actual failure was bare
  `pytest` with *no* arguments, which additionally depends on `testpaths = tests`.
  Neither that invocation nor the `pytest.ini` contents are guarded anywhere.
- **Finding 2, weak CI lock**: `ci.yml` is only substring-asserted. A syntactically
  invalid or structurally regressed workflow (e.g. broken `on:` block, renamed job,
  dropped setup step) would pass the string checks while producing zero checks on
  GitHub — exactly the silent failure mode the reviewer flagged.

## Approach
- Add a no-arguments collection test: run bare `pytest --collect-only -q` from the
  repo root with no path argument and assert both test modules are collected. This
  exercises the ini (`testpaths`) plus both import mechanisms end to end.
- Add a `pytest.ini` shape lock via stdlib `configparser`: `[pytest]` section with
  `pythonpath = .` and `testpaths = tests`.
- Add a real YAML parse of `ci.yml` (`yaml.safe_load`) with structural assertions:
  triggers (`push` on `main`, `pull_request`), `actions/checkout`, `actions/setup-python`,
  and a run step containing `pytest`. Use `pytest.importorskip("yaml")` so environments
  without PyYAML skip cleanly instead of erroring.
- Update the CI install step to `python -m pip install pytest pyyaml` so the YAML
  parse test actually *runs* in CI rather than skipping there.

## Key decisions
- **YAML 1.1 `on` quirk**: PyYAML resolves the bare key `on` to boolean `True`, so the
  trigger block is looked up as `workflow[True]` with a `"on"` fallback. Noted here so
  future readers don't "fix" it.
- **Skip vs. hard-depend on PyYAML**: locally PyYAML may be absent; skipping keeps the
  suite green while CI (which now installs it) still enforces the parse. The cheaper
  substring test stays as an always-on baseline.
- **No `requirements.txt`**: the repo is a two-module toy; the CI install line names
  its only two test dependencies explicitly.
- Tooling-only round again: `primes.py` and `tests/test_primes.py` are untouched.

## Files
- `tests/test_tooling.py` — new tests: no-args bare collection, pytest.ini shape,
  ci.yml YAML parse + structure
- `.github/workflows/ci.yml` — install `pyyaml` alongside `pytest`
- `docs/designs/review-fixes-round3.md`, `docs/test-cases/review-fixes-round3.md` — this round's docs
