# Test Cases: Review Fixes Round 3

Re-audit of the two P3 findings from task-mt17vsshrc (bare `pytest` import failure;
missing CI). Scenarios verify the fixes hold under the findings' literal conditions
and lock the tooling shapes against regression.

## Scenarios (user-facing)
1. **Bare `pytest`, no arguments** (the reviewer's exact command): running
   `pytest --collect-only -q` from the repo root collects the full suite —
   both `tests/test_primes.py` and `tests/test_tooling.py` appear,
   with no `ModuleNotFoundError` and exit code 0. Exercises `testpaths = tests`.
2. **CI workflow parses as YAML**: `ci.yml` loads via `yaml.safe_load` and has the
   expected structure — triggers on `push` (branches: `[main]`) and `pull_request`,
   a `jobs.test` using `actions/checkout` and `actions/setup-python`, and a run step
   invoking `pytest`.

## Edge cases
3. **pytest.ini shape**: `[pytest]` section present with `pythonpath = .` and
   `testpaths = tests` (parsed with stdlib `configparser`, whitespace-tolerant).
4. **YAML 1.1 boolean `on`**: the trigger key is resolved as `True` by PyYAML; the
   test looks up `workflow[True]` with a `"on"` string fallback so either parse
   behaves the same.
5. **CI installs its test deps**: the CI install step names both `pytest` and
   `pyyaml` (without pyyaml the YAML test would skip in CI and enforce nothing).

## Error handling / skip paths
6. **PyYAML unavailable locally**: `pytest.importorskip("yaml")` skips the parse test
   with a clear reason instead of erroring; the cheaper substring-based workflow test
   remains as an always-on baseline.
7. **Bare `pytest` executable missing from PATH**: the no-args test falls back to
   `python -m pytest` so it still runs the scenario instead of skipping.
8. **Subprocess failure diagnostics**: collection subprocess asserts include the
   command, stdout and stderr in the failure message.

## Verification (this round)
- TDD: the pyyaml-install assertion failed against the pre-round `ci.yml`
  (`pytest` only), then passed after the install line was updated.
- Full suite run synchronously both ways: `pytest -q` (bare) and
  `python -m pytest -q` — all green.
