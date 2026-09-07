# Design: FP-010 发布帖子 (Create Post)

Task card: `input/tasks/social-platform/FP-010-create-post.task.md` (sole source of truth).
Trace: UC-005. Wave 3. Stack: Python 3.12 + Flask + SQLite + pytest.

## Goal

Logged-in user submits plain-text content at `GET/POST /posts/new`; after
non-empty (post-trim) and ≤ 1000-char validation the post is persisted
(author, content, created_at from DB default). No edit, no delete (D-006).

## Merge state of strong dependencies (checked at branch time)

- **FP-001 merged** (commit 9713805): `social_app/db.py` provides
  `init_db/execute/query_one/query_all` + `SOCIAL_DB` env routing and the
  `posts`/`users` tables. Reused as-is; no DDL duplication.
- **FP-002 NOT merged** → per task card §6 self-build the minimal Flask shell:
  `social_app/__init__.py` gains `create_app()` / `register_blueprints(app)`
  following the FP-002 embedded contract (secret key from
  `SOCIAL_SECRET_KEY`, default `dev-secret`; blueprint registry). No home
  route / nav — FP-002 merge extends this file. Minimal
  `social_app/templates/base.html` providing the two contract blocks
  (`title`, `content`) plus a flash area.
- **FP-003 NOT merged** → per task card §3.2/§6 self-build the auth contract
  slice `social_app/auth.py`: `login_required` (302 →
  `/login?next=<request.path>`) and `current_user_id()` reading
  `session["user_id"]`. Login state in tests is injected via
  `session_transaction` (mock isolation, integration point I-22 swaps in the
  real FP-003 implementation later).

## Key decisions

1. **Blueprint**: `social_app/posts.py` exposes `bp = Blueprint("posts",
   __name__)` with `GET/POST /posts/new`, exactly as the FP-002 mounting
   contract requires.
2. **Validation** (server-side, on POST only):
   - `content = request.form.get("content", "").strip()` — missing field is
     treated as empty (defensive; the textarea always submits the key).
   - empty after trim → fail with reason 帖子内容不能为空.
   - `len(content) > 1000` → fail with reason 帖子内容不能超过 1000 字符.
   - Boundary: exactly 1000 chars passes; length is measured after trimming
     (the card validates the trimmed content).
   - Failure → re-render the form with the specific reason in the error area,
     HTTP 422 (client-side content error), no DB write.
3. **Persistence**: `db.execute("INSERT INTO posts (author_id, content)
   VALUES (?, ?)", (uid, content))` — `created_at` comes from the column
   default; author = `current_user_id()`.
4. **Success**: flash 已发布 message, 303 redirect back to `/posts/new` (the
   post-publish result view; feed display belongs to FP-011, ledger I-25).
5. **No edit/delete anywhere**: no such routes in the url map, no such
   elements/labels in templates (asserted by tests, D-006).
6. **Templates**: `social_app/templates/posts/new.html` extends
   `base.html`; contains textarea + submit button + error area. User-facing
   copy in Chinese (matches the Chinese spec).
7. **Test isolation** (`tests/test_fp010_posts.py`): fresh temp DB per test via
   `SOCIAL_DB` + `db.init_db()`; seed user `alice` inserted directly with
   `db.execute` (种子直插用户); login via session injection. No HTTP server.

## Files

- `social_app/posts.py` (new) — the feature.
- `social_app/auth.py` (new) — FP-003 contract slice (stand-in until merge).
- `social_app/__init__.py` (edit) — minimal FP-002 shell contract.
- `social_app/templates/base.html`, `social_app/templates/posts/new.html` (new).
- `tests/test_fp010_posts.py` (new), `docs/test-cases/fp010-create-post.md`.
