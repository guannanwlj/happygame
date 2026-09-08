# FP-004 Design: Local Startup & Runtime Configuration

Task card: `input/tasks/social-platform/FP-004-runtime-config.task.md` (sole spec).
Goal: a runnable local chain — `python -m social_app` starts a single-process
development server, `SOCIAL_DB` selects the SQLite file (reusing
`social_app/db.py`), `requirements.txt` lists pip dependencies, and data
survives restarts. Public deployment is explicitly out of scope (deferred
upstream, not in any task).

## Approach

- `social_app/__main__.py` is the whole runtime surface: `main()` calls
  `db.init_db()` (idempotent schema, §3.1) and then
  `create_app().run(host="127.0.0.1", ...)` with Flask's built-in server.
  No routing logic lives here — the entrypoint only "lifts the application"
  (routes belong to FP-001 and the page tasks).
- Per card §6, the app factory is resolved defensively:
  `try: from social_app.app import create_app; except ImportError:` fall back
  to a self-contained minimal factory (`_placeholder_create_app`) serving `/`.
  This keeps the startup chain verifiable inside FP-004 while FP-001 is not
  merged; once it lands, the real factory is picked up automatically with no
  change here.
- Storage is untouched: `SOCIAL_DB` is read at call time by `social_app/db.py`
  (`db_path()`), so the subprocess just inherits the environment. Startup
  calling `init_db()` guarantees the four tables exist in the chosen file
  before the first request.
- `requirements.txt` lists `flask` (werkzeug arrives as its dependency) plus
  `pytest` for the test suite the README tells contributors to run.

## Key decisions

1. **`SOCIAL_PORT` extension (default 5000)**: the card fixes only
   `host="127.0.0.1"`. §8 requires launching the server as a subprocess and
   hitting it over HTTP; a hard-coded port would make tests flaky when 5000 is
   taken (CI, parallel runs). The env var is read at call time, mirroring the
   `SOCIAL_DB` philosophy, and defaults to Flask's own default.
2. **`use_reloader=False`**: guarantees true single-process semantics (the
   reloader would fork a child and complicate shutdown/restart assertions);
   also neutralizes any ambient `FLASK_DEBUG` in the environment.
3. **Fallback factory keeps a `/` route**: the acceptance only demands "GET /
   returns 302 or any route answers"; the placeholder returns 200 with a short
   text, which satisfies it and stays correct once FP-001's real pages exist.
4. **Lazy `flask` import inside the placeholder**: importing
   `social_app.__main__` stays cheap and flask-free until a server/app is
   actually built; unit tests of the entrypoint contract do not need flask.
5. **Restart durability**: SQLite commit-per-write in `db.execute` plus the
   default rollback journal already give "restart does not lose data"; the
   entrypoint adds nothing on top — it just re-runs `init_db()` (a no-op on an
   existing file) on every boot.

## Verification

`python3 -m pytest tests/test_fp004_runtime.py -q`, then the full suite.
Scenarios documented in `docs/test-cases/fp004-runtime-config.md`.
