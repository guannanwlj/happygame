# FP-001 Test Scenarios — Social Platform Web Skeleton

Module under test: `social_app/app.py` + `social_app/__main__.py` (spec: task
card FP-001 §3.2 route table / §7 / §8). Per card §6 no mock framework is
used: a real `ThreadingHTTPServer` runs on a random free port (`port=0`) in
a daemon thread and every request goes through stdlib `urllib.request`.

> The card §8 suggests `tests/test_fp001_web_skeleton.py`, but that name is
> already used by the itinerary skeleton. The social suite is
> `tests/test_fp001_social_web_skeleton.py`.

## A. Acceptance — home & health (card §7)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `GET /` | Mounted by FP-014 as the feed page: anonymous request returns 303 to `/login` (placeholder replaced) |
| A2 | `GET /?debug=1` | Same 303 — query string ignored for routing |
| A3 | `GET /healthz` | 200; body exactly `ok`; `text/plain` content type |

## B. Error / method handling (card §7)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `GET /no-such-path` | 404 plain text (not an unhandled 500) |
| B2 | `POST /` (path exists for GET only) | 405 with `Allow` header containing `GET` |
| B3 | `GET /posts` (path exists for POST only) | 405 with `Allow` header containing `POST` |

## C. Skeleton 501 mount points (card §7)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `GET /register` | 501; body names FP-006 |
| C2 | `POST /register` | 501; body names FP-006 |
| C3 | `GET /login` / `POST /login` / `POST /logout` | 501; body names FP-008 |
| C4 | `GET /posts/new` / `POST /posts` | 501; body names FP-012 |
| C5 | `POST /follow` | 501; body names FP-010 |

## D. Registry extensibility (card §7)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Re-register `POST /register` with a custom handler on `create_app()`, serve it, POST `/register` | 200 with the later handler's output — skeleton 501 is replaced, not shadowed |
| D2 | Register a brand-new `GET /extras/<name>` route, serve, request `/extras/hike` | 200 with parsed `{name}` param |
| D3 | `app.routes` introspection | Contains all ten card §3.2 routes |

## E. Path parameters & rendering safety

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `GET /posts/1/extra` on the served app | 404 — no registered route matches |
| E2 | `Route("GET", "/posts/<id>").match("/posts/1")` | `{"id": "1"}` |
| E3 | `Route(...).match("/posts/1/extra")` | `None` — `<param>` compiles to `[^/]+` and never spans a slash |
| E4 | `render_page(title, body)` with `<script>` in the title | `&lt;script&gt;` present, raw `<script>` absent |
| E5 | `parse_form(b"username=a+b&password=p%40ss&empty=")` | `{"username": "a b", "password": "p@ss", "empty": ""}` |
| E6 | `redirect("/login")` | status 303 and `headers == {"Location": "/login"}` |

## F. Cookies (card §7)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | HTTP request to a mounted `/whoami` handler with `Cookie: session=abc` | handler sees `request.cookies == {"session": "abc"}` |
| F2 | `Cookie: session=abc; theme=dark` | both cookies parsed |
| F3 | No `Cookie` header | `request.cookies == {}` |

## G. Configuration & entry point (card §7)

| # | Scenario | Expected |
|---|----------|----------|
| G1 | `bind_address()` with `SOCIAL_HOST`/`SOCIAL_PORT` unset | `("127.0.0.1", 8000)` |
| G2 | `SOCIAL_HOST=0.0.0.0`, `SOCIAL_PORT=9001` | `("0.0.0.0", 9001)` |
| G3 | `SOCIAL_PORT=http` (non-integer) | `ValueError` naming `SOCIAL_PORT` |
| G4 | `create_server(app, host, port=0)` | Binds a real random free port and serves requests in a daemon thread |

Suite: `tests/test_fp001_social_web_skeleton.py`.
