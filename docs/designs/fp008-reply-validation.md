# FP-008 Design: Reply Level and Content Validation

Task card: `input/tasks/social-comment-interactions/FP-008-reply-validation.task.md`
(sole spec). Goal: add `social_app/reply_service.py` exposing `ReplyError` and
`add_reply(parent_id, author_id, content) -> int`, enforcing one-level nesting
(only top-level comments may be replied to), a non-blank body, and allowing
self-replies, with every rejection raising a readable Chinese error and writing
nothing.

## Approach

- **Rule module, mirroring `comment_service.py`.** FP-018 established the
  "business-rules module over the storage layer, readable-error exception"
  pattern. `reply_service` is the reply-dimension equivalent, so it imports the
  storage module as `from social_app import comments` (module-level name) for
  monkeypatchability and delegates the actual INSERT.
- **No storage changes.** FP-002 already added `comments.parent_id` and
  `comments.get_comment` / `comments.add_comment(..., parent_id=None)`. The
  card's §6 mock fallback (inline `SELECT`) is therefore unnecessary; the
  dependency is present on this branch.
- **Strict validation order** exactly as §4: (1) parent exists, (2) parent is
  top-level (`parent_id IS NULL`), (3) `content.strip()` non-empty. Order
  matters when several rules fail at once; a blank reply to a missing parent is
  reported as "回复对象不存在".
- **Write derives the post from the parent.** `post_id` is never passed in; it
  is read off the parent row so a reply can never land on a different post.
  `parent_id=parent_id`, `author_id=author_id`.
- **No self-reply ban** (D6): no author comparison is performed.
- **Failures happen before any write**, so "rejected implies no new row" is
  structural rather than cleanup-based.

## Key decisions

1. **Reject replies-to-replies by inspecting `parent_id`, not by depth
   recursion.** A single check `parent_row["parent_id"] is not None` is enough
   because the schema keeps nesting one level deep by construction.
2. **`content.strip()` checks emptiness but stores the original string**,
   matching `comment_service.add_comment` (padded content is preserved
   verbatim).
3. **Constants** `PARENT_NOT_FOUND_MESSAGE`, `NOT_TOP_LEVEL_MESSAGE`,
   `BLANK_CONTENT_MESSAGE` are module-level so tests and future routes reference
   one source of truth.
4. **`ReplyError` is a plain `Exception` subclass**, consistent with
   `CommentError` / `InteractionError`; callers catch it and render the message.
5. **The parent row is fetched once** and reused for both validation and the
   `post_id` lookup, keeping the read side to a single query.

## Verification

`python3 -m pytest tests/test_fp008_reply_validation.py -q` then the full
`python3 -m pytest -q`. Scenarios documented in
`docs/test-cases/fp008-reply-validation.md`.
