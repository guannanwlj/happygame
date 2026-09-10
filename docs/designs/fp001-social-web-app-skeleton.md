# FP-001 Design: Social Platform Web App Skeleton

Task card: `input/tasks/social-platform-mvp/FP-001-web-skeleton.task.md`
(sole spec, embedded in the work order). Goal: a startable stdlib-only web
base (`social_app` package) — route registry, request/response objects,
server-side rendered templates and the mount points every later social
feature (FP-006 / FP-008 / FP-010 / FP-012 / FP-014) registers real
handlers onto. Sibling of the existing `itinerary_app/` skeleton; same
engineering conventions.

## Approach

- Extend the existing `social_app/` package (which already holds `db.py`)
  with three modules:
  - `app.py` — reusable core: `Request`/`Response` dataclasses, the `Route`
    pattern compiler, the `SocialApp` registry + dispatcher, the
    `render_page`/`html_response`/`text_response`/`redirect`/`parse_form`
    helpers, the ten skeleton handlers (card §3.2 contract), and the
    `create_app()` / `create_server()` / `bind_address()` factories plus
    `make_handler()`.
  - `__main__.py` — `python3 -m social_app` entry point; resolves the bind
    address from `SOCIAL_HOST` (default `127.0.0.1`) / `SOCIAL_PORT`
    (default `8000`) and serves until Ctrl-C.
  - `__init__.py` — docstring + re-exports of `SocialApp / Request /
    Response / bind_address / create_app / create_server`.
- HTTP stack: `http.server.ThreadingHTTPServer` +
  `BaseHTTPRequestHandler` (HTTP/1.1 with explicit `Content-Length` on every
  response; `daemon_threads = True`; quiet `log_message`). No template
  library — pages are `str.format` templates with `html.escape` applied to
  the title.
- Routing: an ordered registry of `Route(method, pattern, handler)`.
  `<param>` segments compile to `[^/]+` named groups (they match exactly one
  non-slash segment). Dispatch: exact path match, then method match;
  path-match + method-mismatch → 405 with an `Allow` header listing the
  allowed method(s); no path match → 404. Query strings route via
  `urlsplit().path` and are exposed separately as `parse_qs` output, so `/`
  and `/?debug=1` hit the same handler.
- Request cookies are parsed from the `Cookie` header into `Request.cookies`
  (`session=abc; theme=dark` → `{"session": "abc", "theme": "dark"}`) in the
  HTTP handler before dispatch. FP-003 builds session logic on this.
- Skeleton handlers per card §3.2: `GET /` renders a readable feed
  placeholder (title + links to `/login` and `/register`); `GET /healthz`
  returns `200 "ok"` (text/plain); the remaining routes return 501
  text placeholders naming the task that will mount them. All ten routes are
  registered in `create_app()`. (The three login/logout mount points were
  later replaced by real FP-008 handlers; register / posts / follow keep
  their 501 placeholders.)

## Key decisions

1. **Re-register replaces (mount semantics)**: `app.route()` drops any
   existing entry with the same `(method, pattern)` before appending, so a
   later task can mount a real handler over a skeleton 501 without the old
   one shadowing it. This is the central extensibility mechanism for the
   whole project.
2. **Test file name**: the card §8 suggests `tests/test_fp001_web_skeleton.py`
   but that path is already taken by the itinerary skeleton. The social
   suite lives in `tests/test_fp001_social_web_skeleton.py` instead (same
   coverage, no collision).
3. **`parse_form` keeps blank values**: `parse_qs(..., keep_blank_values=True)`
   so `username=&password=` still yields entries; taking the first value per
   name gives the single-value dict later form handlers expect.
4. **No path percent-decoding in the skeleton** — path params are the raw
   path segments; handlers escape on render. Decoding rules belong to the
   mounting tasks if they need them (conscious choice, mirrors
   `itinerary_app`).
5. **Env read at call time**: `bind_address()` resolves `SOCIAL_HOST` /
   `SOCIAL_PORT` per call so tests can monkeypatch and `python -m social_app`
   picks it up at startup. An invalid `SOCIAL_PORT` raises a clear
   `ValueError` naming the variable instead of an opaque `int()` traceback.
6. **Testable factory**: `create_server(app, host, port)` binds immediately
   (tests pass `port=0` for a random free port and serve in a daemon
   thread); requests use stdlib `urllib.request` only, per card §6 (no mock
   frameworks, real HTTP).
7. **Zero runtime deps**: Python 3.12 stdlib only; `pytest` stays a
   dev-only tool.

## Verification

`python3 -m pytest tests/test_fp001_social_web_skeleton.py -q` (plus the
full suite). Scenarios documented in
`docs/test-cases/fp001-social-web-skeleton.md`.
