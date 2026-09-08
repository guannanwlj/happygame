# FP-001 Test Scenarios — Web Application Skeleton

Module under test: `social_app/web/` (spec: task card FP-001 §4/§7/§8).
All tests use the Flask test client against fresh `create_app()` instances —
no database, no shared state.

## A. Acceptance 1 — factory + home page

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `create_app()` | Returns a `Flask` instance |
| A2 | `GET /` on `create_app()` client | 200; body contains site name and guide text |
| A3 | Base layout effectiveness | Home page contains the flash message region markup and the nav area; `home/index.html` extends `base.html` (site chrome present on every page) |
| A4 | Home page has no business data / no dead links | Future feature entries render grayed (no `<a href>` to unimplemented pages) |

## B. Acceptance 2 — blueprint mount rule (probe)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Register a probe blueprint (`GET /__probe__` → fixed text) via `app.register_blueprint(probe_bp)` on a `create_app()` product | `GET /__probe__` → 200 with the fixed text — features need no app instance of their own |
| B2 | `create_app(features=("home",))` explicit features | Home page still registered; `GET /` → 200 |
| B3 | `features=("home", "no_such_module")` | Raises `ImportError` naming the unknown feature (`no_such_module`) with a clear hint |
| B4 | A feature module that exists but exposes no module-level `bp` (synthetic probe) | Clear `ImportError` mentioning the module name |

## C. Acceptance 4 — SECRET_KEY configuration

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `SOCIAL_SECRET_KEY` unset (monkeypatch.delenv) | `app.config["SECRET_KEY"] == "dev-secret-key"` |
| C2 | `SOCIAL_SECRET_KEY=some-test-key` (monkeypatch.setenv) | `app.config["SECRET_KEY"] == "some-test-key"` |

## D. Acceptance — error pages

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `GET /nope` (no such route) | 404 status; friendly Chinese hint rendered (extends base layout) |
| D2 | A route that raises (probe blueprint) | 500 status; friendly error page rendered (non-debug app) |

## E. Regression — existing suite / CLI

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Full `python3 -m pytest -q` | All pre-existing tests pass (primes, tooling, cli, storage, repo hygiene) |
| E2 | `python3 primes.py 50` | Normal CLI output, unchanged |

Skeleton/test file: `tests/test_web_skeleton.py`.
