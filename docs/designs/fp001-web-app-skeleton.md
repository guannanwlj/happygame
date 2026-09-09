# FP-001 Design: Web App Skeleton (Itinerary Planner)

Task card: `input/tasks/itinerary-planner/FP-001-web-app-skeleton.task.md`
(sole spec, embedded in the work order). Goal: a startable stdlib-only web
base (`itinerary_app` package) — route registry + server-side rendered
placeholders for the form/result pages — that every later itinerary feature
(FP-005 / FP-009 / FP-011 / FP-012) mounts onto.

## Approach

- New package `itinerary_app/` (sibling of the existing `social_app`),
  three modules:
  - `app.py` — everything reusable: `Request`/`Response` dataclasses, the
    `Route` pattern compiler, `ItineraryApp` registry+dispatcher, the five
    skeleton handlers (S6 contract), HTML string templates, and the
    `create_app()` / `create_server()` factories.
  - `__main__.py` — `python3 -m itinerary_app` entry point; resolves the
    bind address from `ITIN_HOST` (default `127.0.0.1`) / `ITIN_PORT`
    (default `8000`) and serves until Ctrl-C.
  - `__init__.py` — docstring + re-exports of the factory API.
- HTTP stack: `http.server.ThreadingHTTPServer` +
  `BaseHTTPRequestHandler` (HTTP/1.1 with explicit `Content-Length` on every
  response; `daemon_threads = True`). No template library — pages are
  `str.format` templates with `html.escape` on interpolated values.
- Routing: an ordered registry of `Route(method, pattern, handler)`.
  Patterns support `<param>` segments compiled to `[^/]+` named groups
  (e.g. `/itinerary/<id>`). Dispatch: exact-match one route by path, then by
  method; path-match + method-mismatch → 405 with an `Allow` header;
  no path match → 404. Query strings are parsed separately
  (`urlsplit().path` routes; `parse_qs` for the query dict) so `/` and
  `/?debug=1` hit the same handler.
- Skeleton handlers per S6: `GET /` renders the form-page placeholder
  (title 「行程规划」); `GET /healthz` returns `200 "ok"` (text/plain);
  `POST /generate` and `GET /itinerary/<id>/export.md` return 501 text
  placeholders naming the task that will mount them; `GET /itinerary/<id>`
  renders the result-page placeholder with the 「暂无行程」 guidance copy
  and the escaped itinerary id.
- Handlers receive a `Request` (method/path/params/query/body) and return a
  `Response` — plain data in, plain data out, so tests can call
  `app.dispatch(...)` directly without a socket, and later tasks can mount
  handlers as ordinary functions.

## Key decisions

1. **Re-register replaces (mount semantics)**: `app.route()` drops any
   existing entry with the same `(method, pattern)` before appending. When
   FP-009/FP-011/FP-012 mount real handlers on the same S6 paths, the
   registration order can never shadow them with the skeleton 501s.
2. **No path percent-decoding in the skeleton** — params are the raw path
   segments; values are always `html.escape`d on render (tested with a
   `<script>` id). Decoding rules belong to the mounting tasks if they need
   it; documented here so it is a conscious choice.
3. **Env read at call time**: `bind_address()` resolves `ITIN_HOST` /
   `ITIN_PORT` per call (like `social_app.db_path`), so tests can
   monkeypatch the environment and `python -m itinerary_app` picks it up at
   startup. Invalid `ITIN_PORT` raises a clear `ValueError` instead of an
   opaque `int()` traceback.
4. **Testable factory**: `create_server(app, host, port)` binds immediately
   (tests pass `port=0` for a random free port and serve in a daemon
   thread); requests are made with stdlib `urllib.request` only, per card
   §6 (no mock frameworks, real HTTP).
5. **Quiet handler**: `log_message` is overridden to no-op so the dev
   server and pytest output stay clean; real logging can arrive with
   FP-013's configuration table.
6. **Zero runtime deps**: Python 3.12 stdlib only, matching the project
   convention (`pytest` stays a dev-only tool).

## Verification

`python3 -m pytest tests/test_fp001_web_skeleton.py -q` (plus the full
suite). Scenarios documented in `docs/test-cases/fp001-web-skeleton.md`.
