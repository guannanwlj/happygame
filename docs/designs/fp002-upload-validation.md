# FP-002 Design: Upload Validation Rules

Task card: `input/tasks/post-image-upload/FP-002-upload-validation.task.md`
(sole spec). Goal: extend the service layer (`social_app/posts.py`) with
image-era submission validation — count ≤ 9, extension whitelist
JPEG/PNG/WebP, per-image ≤ 5MB, and "text or at least one image" — plus relax
`create_post` so pure-image posts (decision D-1) can be written. No schema
change; no multipart parsing, no disk writes, no metadata rows (FP-001/003/004/006).

## Approach

All new logic lives in the existing `social_app/posts.py`, keeping the module
the single source of the posting contract:

```python
MAX_IMAGE_COUNT = 9
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}  # lowercase-normalized
MAX_IMAGE_BYTES = 5 * 1024 * 1024

@dataclass
class UploadedImage:
    filename: str
    data: bytes          # size = len(data)

def validate_post_submission(content: str, images: list[UploadedImage]) -> None: ...
def create_post(author_id: int, content: str, image_count: int = 0) -> int: ...
```

- `validate_post_submission` is a pure function (no IO). It runs four checks in
  the fixed order ①→④ from card §3.2 and raises `PostError` with a fixed
  Chinese constant on the **first** failing rule: count → extensions (a full
  pass over all images) → sizes (a second full pass) → blank-without-images.
- Extension check = `os.path.splitext(filename)[1].lower()` membership in
  `IMAGE_EXTENSIONS` (decision D-2: no magic-number sniffing). A filename with
  no/unknown extension therefore fails with the format message.
- `create_post` gains `image_count: int = 0`. The blank-content guard becomes
  `content.strip() == "" and image_count == 0` → `PostError`. With
  `image_count > 0` blank content is stored as-is (D-1 pure-image post,
  `content` TEXT NOT NULL with empty string legal). The default keeps every
  existing caller (`views_post.post_submit`) and test zero-change.
- The four error messages are module-level constants (card §3.2), reusing the
  existing `BLANK_CONTENT_MESSAGE` for ④.

## Key decisions

1. **Two separate passes for ② and ③.** The card's "任一" wording makes the
   format check a property of the whole list evaluated before any size check,
   so `[5MB+1 .png, a.gif]` reports the format message, not the size one.
2. **Validate-before-write stays.** `create_post` still raises before
   `db.execute`, so a rejected submission never leaves a row.
3. **`UploadedImage` is a plain `@dataclass`** matching the card contract;
   `len(data)` is the size, no `os.stat` or filesystem involvement.
4. **Constants, not literals, in raises** so FP-006 can assert/echo them and
   tests import them instead of duplicating strings.

## Verification

`pytest tests/test_fp002_upload_validation.py -q`, then the full `pytest -q`
regression (FP-024 tests must stay green unchanged). Scenarios documented in
`docs/test-cases/fp002-upload-validation.md`.
