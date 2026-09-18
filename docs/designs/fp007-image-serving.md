# FP-007 Design: Image Serving (Post-Image-Upload Epic)

Task card: `input/tasks/post-image-upload/FP-007-image-serving.task.md` (sole
spec; body embedded in the work order). Goal: a logged-in viewer can fetch a
stored image via `GET /images/<storage_name>` and get the raw bytes with the
right `Content-Type`; anything invalid (bad name, missing file, anonymous
request) is a 404 / 303 without leaking the disk layout.

## Approach

Two small changes, no new dependency:

1. **Binary channel in the web layer** (`social_app/app.py`):
   - `Response.body` is widened from `str` to `str | bytes`.
   - `SocialRequestHandler._write` encodes only `str` bodies (UTF-8, exactly
     as before); `bytes` bodies go on the wire unchanged. `Content-Length`
     stays `len(payload)` — now the byte count for both kinds.
   - `create_app()` mounts the new module (`views_image.register(app)`).
2. **New module `social_app/views_image.py`** with the card §3.2 contract:

   ```python
   IMAGE_DIR_ENV = "SOCIAL_IMAGE_DIR"     # read at call time
   DEFAULT_IMAGE_DIR = "uploads"
   def serve_image(request) -> Response   # GET /images/<name>
   def register(app) -> None              # mounts the route
   ```

   Handler flow: `require_login(request)` → guard response returned unchanged
   (303 `/login`, decision D-6); `name` validated against
   `[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)` with `re.fullmatch`; on pass, read
   `image_dir()/name` as bytes and answer `Response(200, body=bytes,
   content_type=...)`; extension map `.jpg/.jpeg → image/jpeg`,
   `.png → image/png`, `.webp → image/webp`. Every failure path is the same
   `text_response("404 Not Found", status=404)` the dispatcher already uses.

## Key decisions

1. **`fullmatch` whitelist regex = the only name authority.** The whole-string
   match (no `^…$` + `match`, which would accept a trailing newline) admits
   `<token>.<ext>` only, so `../` traversal, `%`-encoded names, subpaths,
   unknown extensions and uppercase extensions (`.PNG`) all fall out as 404
   before any filesystem touch. The router also never percent-decodes the
   path, so encoded names reach the check literally and fail it.
2. **Uniform 404, no detail.** Missing file, illegal name and (router-level)
   unknown path share the exact dispatcher wording; the response never
   contains the storage directory or the resolved path.
3. **No database access.** URL-direct-read of the storage file name means no
   `post_images` query (card §3.1); the weak FP-003 dependency is the
   directory/naming convention only, so tests seed files themselves.
4. **Env read at call time, not import time.** `image_dir()` resolves
   `$SOCIAL_IMAGE_DIR` per request (mirrors `db.db_path()`), so tests
   monkeypatch the env without reloading modules and deployment can retarget
   the directory.
5. **`str` behavior untouched.** `_write` only adds an `isinstance(body,
   bytes)` branch; HTML/text responses keep the same UTF-8 + Content-Length
   bytes as before (regression covered by wire-level tests and the suite).
6. **Module-level `require_login` import** gives tests the same patchable
   seam the other view modules expose; `create_app` imports `views_image`
   locally like its siblings to avoid the circular import.

## Verification

`pytest tests/test_fp007_image_serving.py -q` (new file), then `pytest -q` for
the full-suite regression. Scenarios documented in
`docs/test-cases/fp007-image-serving.md`.
