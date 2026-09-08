# FP-004 Test Cases: Local Startup & Runtime Configuration

Source: task card `input/tasks/social-platform/FP-004-runtime-config.task.md`
§7 (acceptance) + §8 (verification method). Automated in
`tests/test_fp004_runtime.py`.

## A. Acceptance 1 — SOCIAL_DB new path: starts, reachable, data lands in that file

| # | Scenario | Given / When / Then |
|---|----------|---------------------|
| A1 | Server starts and answers | Given deps installed and `SOCIAL_DB=<new dir>/new.db`, `SOCIAL_PORT=<free port>`; When `python -m social_app` runs as a subprocess; Then polling `GET /` returns an HTTP status (any non-server-error response counts, incl. 302/404 per card §7). |
| A2 | Startup initializes the chosen file | Same launch; Then the file at the `SOCIAL_DB` path exists and contains all four tables (users / friend_requests / friendships / posts) — verified through a raw `sqlite3.connect` on exactly that path, not the default `social_platform.db`. |
| A3 | Storage-API writes land in that file | While the server runs, insert `(alice, h1)` into users via `db.execute`; Then a raw connection to the `SOCIAL_DB` file finds the row (username + password_hash). |

## B. Acceptance 2 — restart does not lose data

| # | Scenario | Given / When / Then |
|---|----------|---------------------|
| B1 | Data survives stop + restart | Given the server ran with `SOCIAL_DB=<file>` and a users row exists; When the process is terminated and `python -m social_app` starts again on the same file; Then the server answers HTTP again and the users row is still present (raw connection). |

## C. §8 verification items

| # | Scenario | Expectation |
|---|----------|-------------|
| C1 | `init_db()` idempotency | Running `init_db()` repeatedly (standalone ×2 and once with an explicit connection) raises nothing and leaves all four tables intact. |
| C2 | `requirements.txt` exists | File present at repo root. |
| C3 | `requirements.txt` pip-parseable | Every non-empty, non-comment line parses as a valid `packaging.requirements.Requirement` (the requirement grammar pip uses); `flask` is among the names. |

## D. Entrypoint contract (unit level)

| # | Scenario | Expectation |
|---|----------|-------------|
| D1 | Factory resolution | `_load_create_app()` returns a factory whose app answers `GET /` with status < 500 via the Flask test client — holds both for the §6 placeholder (today) and for FP-001's real `create_app` once merged. |
| D2 | Placeholder serves `/` | `_placeholder_create_app()` answers `GET /` with 200. |
| D3 | `main()` order and bind args | With `db.init_db` and the factory monkeypatched, `main()` calls `init_db` first, then `app.run(host="127.0.0.1", port=<SOCIAL_PORT>, use_reloader=False)`. |
| D4 | Default port | With `SOCIAL_PORT` unset, `main()` binds port 5000 (Flask's default). |

## Edge cases & error handling

- Subprocess dies before answering → readiness poll fails fast with the
  captured process output in the assertion message.
- Free-port race → each server start picks a fresh ephemeral port;
  termination uses `terminate()` then escalates to `kill()` after a timeout
  (no orphan processes between tests).
- Tests never touch the repo's default `social_platform.db`: every launch and
  every in-process storage call points `SOCIAL_DB` at a `tmp_path` file
  (`monkeypatch`/subprocess env).
