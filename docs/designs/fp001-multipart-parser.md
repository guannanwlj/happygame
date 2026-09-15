# FP-001 Design: multipart/form-data 解析能力

Task card: `input/tasks/post-image-upload/FP-001-multipart-parser.task.md`
(sole spec; body embedded in the work order). Goal: give the Web layer
(`social_app/app.py`) a stdlib-only multipart/form-data body parser that
extracts text fields and file parts (filename + bytes) in submission order,
plus `Request.headers` wiring — the foundation for the post image-upload
feature. The existing urlencoded path `parse_form` stays untouched.

## Approach

All changes land in `social_app/app.py` (no new module — the card names the
Web layer as the home of the contract):

1. **New dataclasses** (card §3.2):

   ```python
   @dataclass
   class UploadedFile:      # field / filename (UTF-8 decoded) / data bytes
   @dataclass
   class MultipartForm:     # fields dict + files list, defaults empty
   ```

2. **`parse_multipart(body: bytes, content_type: str) -> MultipartForm`**:
   - `_multipart_boundary(content_type)` scans the `;`-separated parameters
     for `boundary=` (case-insensitive key); the value may be quoted — quotes
     are stripped. Missing/empty → `ValueError`.
   - Split the body on the delimiter `b"--" + boundary`. Section 0 is the
     preamble (ignored — browsers send none); the last section must start
     with `b"--"` (closing delimiter) or the structure is unparseable →
     `ValueError`. Everything in between is one part each.
   - Each part section is `\r\n + part + \r\n` (the trailing CRLF belongs to
     the next boundary). Strip both, then split at the first
     `\r\n\r\n` into header block and body bytes; no separator → `ValueError`.
   - Header block: only `Content-Disposition` matters (other part headers
     such as the part's own `Content-Type` are ignored). Its parameters are
     parsed for `name` and `filename` (quoted or bare values; header bytes
     decoded as UTF-8 per the card — filenames like「图片1.png」survive).
     A part without `Content-Disposition`/`name` → `ValueError`.
   - Classification: `filename` **present** (even empty `filename=""`) →
     `UploadedFile` appended to `files` in body order; otherwise the body is
     UTF-8-decoded into `fields`, first occurrence winning for duplicate
     names — the same semantics as `parse_form`.

3. **`Request.headers` wiring**: new field
   `headers: dict[str, str] = field(default_factory=dict)` (keys lowercase).
   `make_handler()._dispatch` fills it from `self.headers.items()` with
   `.lower()` keys. Existing construction sites need no change (default
   empty dict → regression-safe).

## Key decisions

1. **`bytes.split(delimiter)` framing, not regex.** Boundaries are opaque
   byte strings; splitting on the exact delimiter keeps the parser tiny and
   dependency-free, and makes "boundary doesn't match body" naturally fall
   out as too few sections → `ValueError`.
2. **Strict `ValueError` on unparseable structure** (no boundary, no closing
   delimiter, part without header separator or without a name) — the card
   explicitly delegates error presentation to the caller (FP-006), so the
   parser only needs a crisp failure signal.
3. **Duplicate text names keep the first value**, mirroring `parse_form`
   (card calls this out); duplicate file names never merge — order is the
   contract for FP-002/FP-003 consumers.
4. **Empty filename is still a file part** (card: 含空文件名进 files).
5. **No validation/persistence here** — byte passthrough only; count/type/
   size checks belong to FP-002, disk writes to FP-003, orchestration to
   FP-006 (card §5).
6. **`parse_form` untouched**; `_dispatch` gains one constructor kwarg and
   still reads `Cookie` via `self.headers` as before.

## Verification

`python3 -m pytest tests/test_fp001_multipart.py -q`, then full `pytest -q`
for regression. Scenarios in `docs/test-cases/fp001-multipart-parser.md`.
