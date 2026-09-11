# FP-024 Design: Post Persistence Module

Task card: `FP-024-post-persistence.task.md` (sole spec). Goal: add the missing
`social_app/posts.py` so the existing FP-012 posting UI
(`social_app/views_post.py`) can persist posts. The `posts` table already
exists in `social_app/db.py::SCHEMA_SQL`; no schema change is needed.

## Approach

- **One new module `social_app/posts.py`.** It mirrors the thin-wrapper style
  of `social_app/follows.py`: delegate storage to the generic API
  `social_app.db.execute`, which commits and returns a cursor whose
  `lastrowid` is usable.
- Public contract (card §3.2), kept byte-for-byte compatible with the lazy
  caller in `views_post.py`:

  ```python
  class PostError(Exception):
      """发帖失败，message 为面向用户的可读中文原因。"""

  def create_post(author_id: int, content: str) -> int:
      """内容去首尾空白后非空则写入 posts，返回新帖子 id；空白抛 PostError 且不写入。"""
  ```

- `create_post` first trims `content` (`content.strip()`). If the trimmed
  value is empty it raises `PostError("帖子内容不能为空")` **before** touching the
  database, so no row is written for blank input. Otherwise it runs
  `INSERT INTO posts (author_id, content) VALUES (?, ?)` and returns
  `cursor.lastrowid`.
- The stored text is the caller's original `content`, not the stripped value —
  the card specifies trimming purely as the emptiness test (card §1/§4). This
  also preserves FP-012's echoed text semantics.

## Key decisions

1. **No `__init__.py` re-export.** Consumers resolve `from social_app import
   posts`; the package surface stays stable for concurrent wave-1 tasks and
   the lazy import in `views_post._load_posts()` keeps working.
2. **Reuse `db.execute`.** Single connection per call, auto-commit, and
   `lastrowid` available without a second query — consistent with FP-004/FP-011.
3. **Validate before writing.** Raising `PostError` prior to `db.execute`
   guarantees the "blank ⇒ no write" acceptance criterion with no rollback
   logic.
4. **No extra validation.** Author existence relies on the table's foreign key
   (`author_id REFERENCES users(id)`), matching the storage-only scope; login
   guarding remains FP-003/FP-012. Out-of-scope items (feed query, likes,
   comments) are untouched.

## Verification

`python3 -m pytest tests/test_fp024_posts.py -q` (plus the full suite).
Scenarios documented in `docs/test-cases/fp024-post-persistence.md`.
