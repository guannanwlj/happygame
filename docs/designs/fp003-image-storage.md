# FP-003 Design: 图片文件存储（本地磁盘）

Task card: `input/tasks/post-image-upload/FP-003-image-storage.task.md` (sole
spec). Goal: new module `social_app/image_storage.py` exposing the constants
`IMAGE_DIR_ENV` / `DEFAULT_IMAGE_DIR`, the `ImageStorageError` exception, and
the two functions `image_dir` / `save_image`. No database involvement — the
`post_images` metadata table is FP-004 and only stores the `storage_name`
string produced here.

## Approach

- **Env-var pattern mirrors `db.py`** (`social_app/db.py:114-116`): the
  directory is resolved at *call time* via `os.environ.get(IMAGE_DIR_ENV,
  DEFAULT_IMAGE_DIR)` with `DEFAULT_IMAGE_DIR = "uploads"` relative to the
  current working directory.
- **Collision-free naming.** `storage_name = secrets.token_urlsafe(16) +
  <ext>` where `ext = os.path.splitext(original_filename)[1].lower()` (扩展名
  小写归一， `.PNG → .png`). Before using a candidate the module checks
  `os.path.exists` on the full target path and regenerates on collision — a
  repeated upload never overwrites an existing file.
- **Write via temp file + `os.replace`.** The bytes are written with a loop of
  raw `os.write` calls into a hidden `.<storage_name>.part` sibling inside the
  target directory, then atomically renamed onto the final name. Readers
  (FP-007 `/images/<storage_name>`) therefore never observe a half-written
  file. This call shape also matches the card §7 failure-injection points
  (`os.write` / `os.replace`).
- **Directory creation.** `os.makedirs(directory, exist_ok=True)` before
  writing, so a missing directory is auto-created (including parents when the
  env var points at a nested path).
- **Failure semantics = 明确错误＋无残留.** Any `OSError` (directory not
  writable, write failure, replace failure) triggers best-effort unlink of the
  `.part` temp file (errors suppressed) and then raises `ImageStorageError`
  with a readable Chinese message; the original `OSError` is chained via
  `from`. On failure the target directory contains no new file from this call.

## Key decisions

1. **Temp file in the same directory** guarantees `os.replace` stays an
   atomic same-filesystem rename.
2. **`os.O_CREAT | os.O_EXCL` for the temp file** protects against two
   concurrent saves generating the same token (loop regenerates on
   `FileExistsError`).
3. **Extension may be empty** (`splitext("photo")[1] == ""`): the card only
   mandates lower-case normalization, so a name without an extension yields a
   bare token — no special casing.
4. **No `__init__.py` re-export**, matching the `likes`/`follows` precedent:
   consumers import `social_app.image_storage` directly.
5. **Out of scope** (per card §5): image validation (FP-002), metadata rows
   (FP-004), the GET route (FP-007), thumbnails (D-5 deferred).

## Verification

`python3 -m pytest tests/test_fp003_image_storage.py -q` plus the full suite.
Scenarios documented in `docs/test-cases/fp003-image-storage.md`. The
chmod-0o500 acceptance is skipped under root (root ignores directory
permissions), where write-failure injection covers the same path.
