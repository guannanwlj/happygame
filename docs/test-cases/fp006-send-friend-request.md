# FP-006 Test Scenarios — Send Friend Request

Module under test: `social_app/friends_request.py` (route `POST
/friends/requests`) plus the `social_app/auth.py` contract slice it consumes
(spec: task card FP-006 §4/§6/§7/§8). Every test runs against a fresh
temporary DB (`SOCIAL_DB`), a minimal self-built Flask shell (FP-002 not
merged, §6), and a login state injected via `session_transaction()`
(FP-003 not merged, §6). Seed users per §6: `alice`/`bob`/`carol`;
per-test pre-states are composed from helpers (friendship pair, rejected
request, pending request) because the acceptance scenarios require mutually
exclusive pre-states (e.g. a successful alice→bob needs no bob→alice
pending, unlike the full §6 seed).

## A. Acceptance scenarios (card §7, one GWT each)

| # | Given | When | Then |
|---|-------|------|------|
| A1 | alice、bob 非好友且相互无未处理请求 | alice 以 `username=bob` POST | 200；body `好友请求已发送`；库中新增一条 requester=alice、addressee=bob、status=`pending` |
| A2 | 目标用户名不存在（`ghost`） | alice POST | 400；body `用户不存在`；friend_requests 零行 |
| A3 | 目标是自己（alice → `alice`） | alice POST | 400；body `不能加自己`；零行 |
| A4 | alice–carol 已是好友（friendships 双向行） | alice 以 `username=carol` POST | 400；body `已是好友`；零行（§6 种子） |
| A5 | alice→bob 已存在 pending | alice 再次以 `username=bob` POST | 400；body `已有待处理请求`；该方向 pending 计数仍为 1 |
| A6 | alice→bob 历史请求为 rejected | alice 再次 POST | 200；产生新的 pending（requester=alice、addressee=bob）；历史 rejected 行保留，该方向 pending 计数=1 |

## B. Validation edges (§4 等价实现)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | 反向 pending：bob→alice pending 存在（§6 种子），alice 向 bob 发起 | 400 `已有待处理请求`；不新增 alice→bob 行，库中该配对请求总数仍为 1 |
| B2 | 已是好友的反方向：carol 向 alice 发起（种子 friendships 对称） | 400 `已是好友`；零行（双向查询生效） |
| B3 | 表单缺 `username` 字段 | 400 `用户不存在`；零行 |
| B4 | `username` 为空串 / 纯空白 | 400 `用户不存在`；零行 |
| B5 | `username` 带首尾空白（`" bob "`） | 去除空白后精确匹配 → 成功 200，pending 落库 |
| B6 | 用户名大小写不同（`Bob`） | 精确匹配失败 → 400 `用户不存在`；零行 |

## C. 认证与路由契约（§3.2）

| # | Scenario | Expected |
|---|----------|----------|
| C1 | 未登录（session 无 `user_id`）POST `/friends/requests` | 302；`Location` 指向 `/login?next=/friends/requests`；零行落库 |
| C2 | GET `/friends/requests`（列表属 FP-007，本任务只挂 POST） | 405 |

## D. 状态机与存储兜底（§3.1）

| # | Scenario | Expected |
|---|----------|----------|
| D1 | rejected 历史与新 pending 并存（A6 后再查库） | 配对请求总数=2：一条 rejected（原行未变）+ 一条 pending |
| D2 | accepted 历史存在但当前非好友（数据面） | accepted 不阻塞新发起（对 accepted/rejected 历史不判重） |

Skeleton/test file: `tests/test_fp006_friend_request.py`.
