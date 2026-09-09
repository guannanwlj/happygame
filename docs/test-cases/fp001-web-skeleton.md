# FP-001 Test Scenarios — Web App Skeleton (Itinerary Planner)

Module under test: `itinerary_app/app.py` + `itinerary_app/__main__.py`
(spec: task card FP-001 §3.2 S6 / §7 / §8). Per card §6 no mock framework
is used: a real server runs on a random free port (`port=0`) in a daemon
thread and all requests go through stdlib `urllib.request`.

## A. Acceptance — S6 routes (card §7)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `GET /` | 200; `Content-Type: text/html`; body contains the form-page placeholder structure incl. title 「行程规划」 and a placeholder marker |
| A2 | `GET /healthz` | 200; body exactly `ok`; `text/plain` content type |
| A3 | `GET /itinerary/abc` | 200; HTML result-page placeholder with 「暂无行程」 guidance copy (no 500, no error for unknown id) |
| A4 | `POST /generate` (with form body) | 501 skeleton placeholder (mount point reserved for FP-009); request body is read without hanging |
| A5 | `GET /itinerary/abc/export.md` | 501 skeleton placeholder (mount point reserved for FP-012) |

## B. Router behavior

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `GET /?debug=1` | Query string ignored for routing → same 200 form page as A1 |
| B2 | `GET /no-such-path` | 404 plain-text response (not an unhandled 500) |
| B3 | `GET /generate` (path exists for POST only) | 405 with an `Allow` header listing `POST` |
| B4 | `POST /` (path exists for GET only) | 405 with an `Allow` header listing `GET` |
| B5 | `GET /itinerary/abc/extra` (param pattern is `[^/]+`) | 404 — no accidental match of the export route |

## C. Registry extensibility (later tasks mount here)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Register a new `GET /extras/<name>` route on an app, serve it, request `/extras/hike` | 200 with the new handler's output and the parsed `{name}` param |
| C2 | Re-register `POST /generate` with a custom handler | The later registration wins (200) — skeleton 501 handler is replaced, not shadowed |
| C3 | `app.routes` introspection | Contains all five S6 routes (`GET /`, `GET /healthz`, `POST /generate`, `GET /itinerary/<id>`, `GET /itinerary/<id>/export.md`) |

## D. Rendering safety

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `dispatch(GET /itinerary/<script>)` directly (no socket) | 200; id HTML-escaped (`&lt;script&gt;`), no raw `<script>` in body |
| D2 | Result page includes a link back to the form page (`href="/"`) | Present in placeholder HTML |

## E. Configuration & entry point

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `bind_address()` with `ITIN_HOST`/`ITIN_PORT` unset | `("127.0.0.1", 8000)` |
| E2 | `ITIN_HOST=0.0.0.0`, `ITIN_PORT=9001` | `("0.0.0.0", 9001)` |
| E3 | `ITIN_PORT=http` (non-integer) | `ValueError` naming `ITIN_PORT` |
| E4 | `create_server(app, port=0)` | Binds a random free port; `server.server_address[1] > 0`; serving in a thread answers requests |

Skeleton/test file: `tests/test_fp001_web_skeleton.py`.
