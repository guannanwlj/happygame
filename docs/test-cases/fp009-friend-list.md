# Test Cases: FP-009 我的好友列表 (My Friend List)

Source: task card FP-009 §7 acceptance + §8 suggested tests (card file
absent — scenarios reconstructed from the in-repo contract references, see
`docs/designs/fp009-friend-list.md`).
File: `tests/test_fp009_friend_list.py`.
Command: `python3 -m pytest tests/test_fp009_friend_list.py -q`.

## Fixture / mock isolation (task-card §6 style)

- Fresh temp SQLite DB per test (`SOCIAL_DB` → tmp file) + `db.init_db()`
  (FP-001 merged, real storage used).
- Seed users and the **symmetric** `friendships` row pairs (any
  `created_at`) inserted directly via `db.execute` (FP-008 not merged →
  direct seeding of exactly the rows its accept flow writes; same Mock
  strategy FP-008's own tests used for pre-states).
- Login state injected via `client.session_transaction()["user_id"]`
  (FP-003 not merged → session injection, integration point I-22).
- App built by the minimal `create_app()` shell (FP-002 not merged →
  self-built mounting shell). No HTTP server.

## Scenarios

### S1 列表主路径（自己的好友全部展示）
Given logged-in `alice` befriended with `bob` and `carol` (both symmetric
pairs present, FP-008 accept outcome), When GET `/friends`, Then 200, HTML
page contains both friend usernames and each friendship's `created_at`
(成为好友时间).

### S2 对称存储只渲染一次（不因双行而重复）
Given logged-in `alice` with the alice–bob pair stored as two rows
`(alice,bob)` + `(bob,alice)`, Then the page shows `bob` **exactly once**
(own-direction query; no dedup needed, no duplicates rendered).

### S3 只显示自己的好友（别人的好友不串页）
Given logged-in `alice`; alice–bob friends AND bob–carol friends, Then
alice's list contains `bob` and **not** `carol`; conversely carol's list
contains `bob` and not `alice` (both directions of a pair are visible to
their owners — checked from both sides).

### S4 新的在前（created_at DESC, id DESC 兜底）
Given logged-in `alice` with three friendships seeded with explicit
distinct `created_at` values, Then they appear newest-first in the rendered
page (position of each username follows the seeded timestamps).

### S5 空列表（登录且无好友）
Given logged-in `alice` with no `friendships` rows for her (even with other
users' pairs present), Then 200 and page shows 暂无好友.

### S6 未登录拦截
Given no `user_id` in session, When GET `/friends`, Then 302 to
`/login?next=/friends`.

### S7 页面骨架契约（FP-002 模板继承）
Given the rendered page, Then it is HTML with a `<title>` (我的好友) and the
content heading — i.e. it fills the two base blocks; content type
`text/html`.

### S8 用户名 HTML 转义（自动转义）
Given a friend whose username contains `<b>bold</b>`-style markup, Then the
raw tag does not appear in the page; the escaped form does (no HTML
injection through usernames).

### S9 陈旧会话退化为空列表
Given `session["user_id"]` pointing at a user id that has no `users` row,
Then GET `/friends` is 200 with the empty state (no crash, no rows).

### S10 只读页面（GET-only，POST 拒绝）
Given the mounted app, Then the URL map exposes `/friends` for GET and
`POST /friends` → 405 (read-only view; no side-effect surface).

### S11 数据不变（只读）
Given logged-in `alice` with two friendship pairs, When GET `/friends`,
Then the `friendships` table content is identical before and after (the
view never writes).

## Non-assertions (transitional states, cf. FP-002 design decision 8)

- No assertion on the flash area being empty/filled (rendered by
  `base.html`; FP-002's richer layout lands with its merge).
- No assertion about un-friend action links (later feature; no route exists
  yet).
- No assertion on `GET /feed` or `/posts/new` (other tasks' routes).
