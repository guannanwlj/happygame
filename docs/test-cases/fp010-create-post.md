# Test Cases: FP-010 发布帖子

Source: task card §7 acceptance criteria + §8 suggested tests.
File: `tests/test_fp010_posts.py`. Command: `python3 -m pytest tests/test_fp010_posts.py -q`.

## Fixture / mock isolation (task card §6)

- Fresh temp SQLite DB per test (`SOCIAL_DB` → tmp file) + `db.init_db()`
  (FP-001 merged, real storage used).
- Seed: user `alice` inserted directly via `db.execute` (种子直插用户).
- Login state injected via `client.session_transaction()["user_id"]` (FP-003
  not merged → session injection, I-22).
- App built by the minimal `create_app()` shell (FP-002 not merged →
  self-built mounting shell).

## Scenarios

### S1 成功发帖（三要素落库）
Given logged-in alice, When POST valid content ("hello world"),
Then 303 → `/posts/new`; followed page shows success message; DB gains
exactly 1 row with author_id=alice.id, content identical, created_at
non-empty (ISO-ish timestamp).

### S2 首尾空白被去除后落库
Given logged-in alice, When POST `"  hello  "`,
Then saved content is `"hello"` (trimmed before validation/persist).

### S3 空内容失败（空串 / 全空白 / 缺字段）
Given logged-in alice, When POST `""`, or `"   \n\t  "`, or a form without
the `content` key, Then response is 422, shows 帖子内容不能为空, and posts
row count is unchanged (0 new rows).

### S4 超长失败（>1000 字符）
Given logged-in alice, When POST 1001+ chars, Then 422, shows
帖子内容不能超过 1000 字符, no new posts row.

### S5 边界：恰好 1000 字符成功
Given logged-in alice, When POST exactly 1000 chars, Then saved
(content round-trips, length 1000).

### S6 未登录 GET 被拦截
Given no session, When GET `/posts/new`, Then 302 to
`/login?next=/posts/new`.

### S7 未登录 POST 被拦截且不落库
Given no session, When POST valid content, Then 302 to
`/login?next=/posts/new` and posts table stays empty.

### S8 表单页可达且含发帖控件
Given logged-in alice, When GET `/posts/new`, Then 200, page contains the
textarea (`name="content"`) and a submit button, plus the error area
element (empty on GET).

### S9 无编辑/删除入口（D-006）
- Given logged-in alice, When GET the form page and the post-success result
  page, Then rendered HTML contains no 编辑/删除 controls (no such labels,
  no edit/delete-ish form actions).
- App url map contains no rule other than the static-only and
  `/posts/new` posts rule — i.e. no edit/delete routes exist.

### S10 长度按去空白后判定（trim 参与长度校验）
Given logged-in alice, When POST 1002 raw chars whose trimmed length is
1000, Then success (validation happens after trim).
