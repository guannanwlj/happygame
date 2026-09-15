# FP-007 Test Scenarios — Image Serving (Post-Image-Upload Epic)

Module under test: `social_app/views_image.py` (`serve_image`,
`register`, `image_dir`) plus the widened `social_app.app.Response` /
`_write` binary channel (spec: task card FP-007 §7/§8). Per card §6 no FP-003
writer is invoked: the image directory is a temp dir
(`monkeypatch.setenv("SOCIAL_IMAGE_DIR", ...)`) seeded with files written
directly, and the login state is a seed user in a temp `SOCIAL_DB` plus a real
`session.create_session(uid)` token. In-process dispatch covers the handler;
one class drives a real `ThreadingHTTPServer` with `http.client` for the
wire-level byte/`Content-Length` checks.

Seeds: `seed.png` (`b"\x89PNG\r\n\x1a\n"` + 256 byte ramp), `seed.jpg`,
`seed.jpeg`, `seed.webp` (binary junk with correct magic), `outside.png`
(sibling of the image dir, for the traversal probe).

## A. Logged-in serving (acceptance 1)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Logged-in, `GET /images/seed.png` | 200, `body` is `bytes`, byte-identical to the disk file, `Content-Type: image/png` |
| A2 | Same with `seed.jpg` | 200, bytes identical, `Content-Type: image/jpeg` |
| A3 | Same with `seed.jpeg` | 200, bytes identical, `Content-Type: image/jpeg` |
| A4 | Same with `seed.webp` | 200, bytes identical, `Content-Type: image/webp` |
| A5 | Serving does not need the DB | no `SOCIAL_DB`-touching code path (handler reads only the storage dir) |

## B. Anonymous (acceptance 2)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | No cookie, `GET /images/seed.png` (file exists) | 303, `Location == /login` (guard semantics, D-6) |
| B2 | Guard response is returned unchanged | the response is the guard object itself |

## C. Missing file (acceptance 3, first half)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Logged-in, `GET /images/nope.png` (never seeded) | 404 |
| C2 | Same response | plain-text body, no storage dir path / `uploads` fragment leaked |

## D. Illegal names (acceptance 3, second half)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Uppercase extension `seed.PNG` (file exists on disk) | 404 |
| D2 | Unknown extension `seed.gif` | 404 |
| D3 | `%`-encoded name `seed%2Epng` / `..%2Fseed.png` | 404 (router does not decode; regex rejects) |
| D4 | No-extension / doubled-dot / trailing-newline names | 404 |
| D5 | Multi-segment path `/images/../outside.png` | 404 (router only matches one segment) |
| D6 | Handler probed directly with `params={"name": "../outside.png"}` while `outside.png` exists next to the image dir | 404 — the directory-external file is never read |

## E. Route wiring / method contract

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `create_app()` routes | `("GET", "/images/<name>")` registered |
| E2 | `views_image.register` on a bare `SocialApp` | same route registered |
| E3 | `POST /images/seed.png` | 405 with `GET` in `Allow` |
| E4 | `image_dir()` | `$SOCIAL_IMAGE_DIR` when set, `uploads` default otherwise |

## F. Binary channel / wire regression (acceptance 4 + 5)

Real server on a free port, `http.client` requests (no redirect following):

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Wire `GET /images/seed.png` with session cookie | 200, raw response bytes identical, `Content-Length == len(bytes)` (byte count, not char count), `Content-Type: image/png` |
| F2 | Wire `GET /healthz` | 200, `ok`, `text/plain; charset=utf-8` unchanged |
| F3 | Wire `GET /` with cookie | 200, `text/html; charset=utf-8`, `Content-Length == len(body.encode("utf-8"))` (UTF-8 regression) |
| F4 | Wire `GET /images/seed.png` without cookie | 303, `Location: /login` (no redirect followed) |

Skeleton/test file: `tests/test_fp007_image_serving.py`.
