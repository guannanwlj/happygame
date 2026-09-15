# FP-002 Test Scenarios — Upload Validation Rules

Module under test: `social_app/posts.py` (`validate_post_submission`,
`UploadedImage`, constants, relaxed `create_post`) against the existing
`posts` table (spec: task card FP-002 §3.2/§7/§8). DB-backed tests use a fresh
temp database via `SOCIAL_DB` + `db.init_db()` + one seeded user (same autouse
fixture pattern as `tests/test_fp024_posts.py`). Image bytes are arbitrary —
only extension and length matter.

Helpers: `PNG_IMG` (valid sample) and `sized(name, n)` (exact-length image).

## A. Acceptance 1 — more than 9 images

| # | Scenario | Expected |
|---|----------|----------|
| A1 | 10 valid `.png` images, `validate_post_submission("", imgs)` | `PostError`, message `图片数量不能超过 9 张` |

## B. Acceptance 2 — extension whitelist

| # | Scenario | Expected |
|---|----------|----------|
| B1 | 3 images, 2nd is `a.gif` | Whole submission rejected, message `图片格式仅支持 JPEG/PNG/WebP` |
| B2 | Uppercase `.PNG` / `.JPEG` extensions | Pass (lowercase-normalized judgment) |

## C. Acceptance 3 — per-image size limit

| # | Scenario | Expected |
|---|----------|----------|
| C1 | One `.png` of exactly `5MB + 1` bytes | `PostError`, message `单张图片不能超过 5MB` |
| C2 | One `.png` of exactly 5MB (== limit) | Pass (strictly-greater rejection) |

## D. Acceptance 4 — blank text + ≥1 valid image (D-1)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `validate_post_submission("  ", [PNG_IMG])` | Pass, no exception |
| D2 | `create_post(uid, "  ", image_count=1)` | Row written; `content` stored unchanged (`"  "`); returns int id |

## E. Acceptance 5 — blank text + no image

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `validate_post_submission("  ", [])` | `PostError` `帖子内容不能为空` |
| E2 | `create_post(uid, "  ")` (default `image_count`) | `PostError`, no row written (status quo unchanged) |

## F. Acceptance 6 — text-only post (regression)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `validate_post_submission("hello", [])` | Pass |
| F2 | `create_post(uid, "hello")` | Behaves exactly as before; existing `tests/test_fp024_posts.py` stays green with zero edits |

## G. Edge cases / determinism

| # | Scenario | Expected |
|---|----------|----------|
| G1 | Exactly 9 valid images | Pass |
| G2 | 10 images where one is also `.gif` | Count message wins (order ① before ②) |
| G3 | Oversize image before a `.gif` in the list | Format message wins (② full pass precedes ③) |
| G4 | Uppercase `.JPG` (case-insensitive whitelist) | Pass |
| G5 | No extension / unknown extension (`a.txt`, `noext`) | Format message |
| G6 | `image_count=2` with blank content | Row written once (D-1) |
| G7 | Constants exported | `MAX_IMAGE_COUNT == 9`, `MAX_IMAGE_BYTES == 5 * 1024 * 1024`, `IMAGE_EXTENSIONS == {".jpg", ".jpeg", ".png", ".webp"}` |

Skeleton/test file: `tests/test_fp002_upload_validation.py`.
