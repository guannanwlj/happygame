# Test Cases: FP-007 好友请求待处理列表

Source: task card FP-007 §7 acceptance + §8 suggested tests (card file absent
— scenarios reconstructed from the in-repo contract references, see
`docs/designs/fp007-pending-request-list.md`).
File: `tests/test_fp007_pending_requests.py`.
Command: `python3 -m pytest tests/test_fp007_pending_requests.py -q`.

## Fixture / mock isolation (task-card §6 style)

- Fresh temp SQLite DB per test (`SOCIAL_DB` → tmp file) + `db.init_db()`
  (FP-001 merged, real storage used).
- Seed users and `friend_requests` rows (any status / `created_at`) inserted
  directly via `db.execute` (FP-006 not merged → direct seeding, same Mock
  strategy FP-006's own tests used for pre-states).
- Login state injected via `client.session_transaction()["user_id"]`
  (FP-003 not merged → session injection, integration point I-22).
- App built by the minimal `create_app()` shell (FP-002 not merged →
  self-built mounting shell). No HTTP server.

## Scenarios

### S1 列表主路径（收到的 pending 全部展示）
Given logged-in `alice` with pending incoming requests from `bob` and
`carol`, When GET `/friends/requests`, Then 200, HTML page contains both
requester usernames and each request's `created_at`.

### S2 只显示收到方向（发出的不进列表）
Given logged-in `alice`; `bob→alice` pending AND `alice→carol` pending,
Then alice's list contains `bob` and **not** `carol` (sent requests are the
addressee's queue, not the sender's).

### S3 只显示 pending 状态（历史不进列表）
Given logged-in `alice`; incoming rows with status `pending` (`bob`),
`rejected` (`carol`), `accepted` (`dave`), Then only `bob` appears.

### S4 新的在前（created_at DESC, id DESC 兜底）
Given logged-in `alice` with three pending incoming requests seeded with
explicit distinct `created_at` values, Then they appear newest-first in the
rendered page (position of each username follows the seeded timestamps).

### S5 每条按请求 id 寻址接受/拒绝入口（I-17）
Given pending rows with known ids, Then each row contains literal hrefs
`/friends/requests/<id>/accept` and `/friends/requests/<id>/reject` with
link texts 接受 / 拒绝.

### S6 空列表（登录且无待处理）
Given logged-in `alice` with no incoming pending requests (and even with
non-pending history present), Then 200 and page shows 暂无待处理请求，
no accept/reject hrefs.

### S7 未登录拦截
Given no `user_id` in session, When GET `/friends/requests`, Then 302 to
`/login?next=/friends/requests`.

### S8 页面骨架契约（FP-002 模板继承）
Given the rendered page, Then it is HTML with a `<title>` (待处理好友请求)
and the content heading — i.e. it fills the two base blocks; content type
`text/html`.

### S9 用户名 HTML 转义（自动转义）
Given a pending request whose requester username contains
`<b>bold</b>`-style markup, Then the raw tag does not appear in the page;
the escaped form does (no HTML injection through usernames).

### S10 陈旧会话退化为空列表
Given `session["user_id"]` pointing at a user id that has no `users` row,
Then GET `/friends/requests` is 200 with the empty state (no crash, no
rows).

## Non-assertions (transitional states, cf. FP-002 design decision 8)

- No assertion on `POST /friends/requests` (owned by FP-006, not merged
  here; freezing its 405 would break FP-006's merge).
- No assertion that the accept/reject hrefs resolve (FP-008 routes land
  later; I-17 only fixes the addressing scheme).
