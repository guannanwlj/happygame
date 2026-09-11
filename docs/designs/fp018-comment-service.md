# FP-018 Design: Comment Service (create / list / non-blank validation)

Task card: `FP-018-comment-service.task.md` (sole spec; body embedded in the
work order). Goal: add a self-contained business-rule module
`social_app/comment_service.py` that validates comment content, delegates the
write to FP-016's storage, and exposes the post's comments via the storage
reader.

## Approach

- One new module `social_app/comment_service.py`; no existing runtime code is
  touched. It leans on the landed FP-016 storage module
  `social_app.comments` (`add_comment`, `list_comments`).
- Public contract (card §3.2):

  ```python
  class CommentError(Exception):
      """评论失败，message 为面向用户的可读中文原因。"""

  def add_comment(post_id: int, author_id: int, content: str) -> int
  def list_comments(post_id: int) -> list
  ```

- Rule evaluation (card §4):

  1. `content.strip() == ""` → `raise CommentError("评论内容不能为空")`
     **before** any write, so rejected requests leave `comments` untouched.
  2. otherwise `return comments.add_comment(post_id, author_id, content)`.
  3. `list_comments(post_id)` is a straight pass-through of
     `comments.list_comments(post_id)`, preserving the storage ascending order.

- Storage is referenced through the **module-level name** `comments`
  (`from social_app import comments`; calls are `comments.add_comment(...)`).
  This keeps the dependency monkeypatchable — tests can replace
  `comment_service.comments` with an in-memory fake — while avoiding the name
  collision that a `from social_app.comments import add_comment` would cause,
  since this module's own public function is also named `add_comment`.

## Key decisions

1. **Service owns the rule, storage owns the row.** The service never issues
   SQL; it only rejects blank content and delegates. The `(post_id, author_id,
   content)` shape and `created_at` default stay in FP-016.
2. **`CommentError` subclasses `Exception`.** Callers (FP-021) catch this
   dedicated type and render `str(exc)` directly as the user-facing message.
3. **Validation uses `strip()`, storage keeps the original text.** A
   whitespace-padded but non-blank body is accepted and stored verbatim,
   matching the existing `social_app.posts.create_post` behaviour.
4. **No side effects on rejection.** The blank check short-circuits before the
   storage call, so `comments` row count is unchanged (card §7).
5. **No permission / ownership logic.** Whether the author may comment belongs
   to FP-019; this module is a pure rule + delegation layer.
6. **No HTTP / rendering.** Routes and redirects are FP-021, feed rendering is
   FP-022; this module has no web concerns.

## Verification

`python3 -m pytest tests/test_fp018_comment_service.py -q` then the full suite
`python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp018-comment-service.md`.
