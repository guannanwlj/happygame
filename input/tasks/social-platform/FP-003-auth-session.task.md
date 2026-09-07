# 任务 FP-003：认证与会话管理

> 来源：FP-003（源 EN-002 认证底座：密码哈希、会话建立保持销毁、未登录拦截｜权限与安全控制）｜
> 优先级 P0｜里程碑 M1（地基能力）｜并发波次 2
> 强依赖（集成前置，编码不阻塞——所需契约已内嵌 §3，未实现按 §6 Mock）：
> FP-001 核心数据模型与持久化存储（认证读写 users 凭据表）；
> FP-002 Web 服务与应用骨架（认证路由挂载与登录跳转引导）
> 弱依赖（联调项）：无
> 独立性：本任务自包含，可独立编码与验证（§1–§8 全部内容；联调信息见 INTEGRATION.md，与本卡无关）

## 1. 目标

交付密码哈希存储与校验、登录会话的建立/保持/销毁、受保护功能的登录态拦截（未登录拒绝并引导登录页），即模块 `social_app/auth.py`。

## 2. 系统上下文（自包含）

本项目是一个社交平台（注册、登录、好友、发帖、好友动态）。用户凭据为用户名+密码（D-004），密码绝不以明文落盘；发帖/好友/动态均为受保护功能，需登录态。本任务是这些约束的统一执行者：哈希算法、会话操作、`login_required` 拦截器一处实现、处处复用。

技术栈（已确认）：Python 3.12 + Flask + SQLite + pytest。会话用 Flask 内置 session（签名 Cookie）。

## 3. 前置契约（已内嵌，无需去别处查找）

### 3.1 数据表（本任务涉及）

```sql
-- 用户（切片；最终实现以 FP-001 数据库任务产出合并，差异走集成点 I-01）
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    NOT NULL UNIQUE,
  password_hash TEXT    NOT NULL,
  created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
```

### 3.2 依赖能力契约（其他任务负责实现，本任务按此调用）

- FP-001 存储能力（签名如下；若未实现，按 §6 以临时 SQLite 文件+内嵌 users DDL 自建等价环境）：

```python
# social_app/db.py（切片）
def db_path() -> str: ...                                  # SOCIAL_DB 环境变量，缺省 social_platform.db
def get_connection() -> sqlite3.Connection: ...            # row_factory=Row, foreign_keys=ON
def init_db(conn=None) -> None: ...                        # 幂等建表
def query_one(sql, params=()) -> sqlite3.Row | None: ...
def execute(sql, params=()) -> sqlite3.Cursor: ...         # 内部 commit
```

- Flask 应用上下文（FP-002 `create_app()` 提供 `secret_key` 与路由挂载；若未实现，按 §6 测试内自建最小 Flask 壳）。

本任务对外提供**认证契约**（FP-004/005/006/010/011 按此调用，本任务为契约源）：

```python
# social_app/auth.py
def hash_password(plain: str) -> str
    # PBKDF2-HMAC-SHA256 + 随机盐；自包含格式 "pbkdf2:sha256$<iterations>$<salt_hex>$<hash_hex>"
    # 语义等价于 werkzeug.security.generate_password_hash(method="pbkdf2:sha256")
def verify_password(plain: str, stored: str) -> bool
    # 按存储格式重算并常数时间比较；stored 格式非法返回 False
def login_user(user_id: int) -> None      # Flask session['user_id'] = user_id
def logout_user() -> None                 # session.clear()
def current_user_id() -> int | None       # session.get('user_id')
def login_required(view)                  # 装饰器：未登录 → 302 redirect("/login?next=<request.path>")
```

### 3.3 外部系统契约

无。

## 4. 实现范围

- 要做：`social_app/auth.py`（上方 API 全量；哈希可用 `werkzeug.security` 或等价 `hashlib.pbkdf2_hmac` 实现，输出格式须满足契约）；
- `login_required` 装饰器（302 至 `/login?next=<原路径>`）；
- 单元测试 `tests/test_fp003_auth.py`。

## 5. 非范围（由其他任务负责）

- 不做注册页/登录页界面与表单流程（由 FP-004 用户注册、FP-005 用户登录与登出 负责），本任务只提供其调用的哈希/会话能力；
- 不做具体受保护业务路由（发帖/好友/动态各自任务用 `@login_required` 装饰自己的视图）；
- 不做 users 表的建表与通用存取（由 FP-001 负责）。

## 6. Mock 与种子数据策略

- 依赖未实现时：FP-001 未合入 → 测试内以 §3.1 内嵌 DDL 在 `tmp_path` 下自建临时库（设 `SOCIAL_DB` 指向）；FP-002 未合入 → 测试内 `Flask(__name__)` + `secret_key` 自建最小壳，并注册一个受保护 dummy 路由验证拦截；
- 验证用种子数据：种子用户 `alice`（`password_hash = hash_password("alice-pass-123")`）；
- 外部系统：无。

## 7. 验收标准（单任务可验证）

- Given 任意明文密码 When `hash_password` 后落库、`verify_password` 校验 Then 哈希串≠明文、含随机盐（两次哈希同密码结果不同）、正确明文验真/错误明文验假——明文不落盘；
- Given 未登录（session 无 user_id） When 访问被 `@login_required` 保护的 dummy 路由 Then 302 跳转 `/login?next=<原路径>`；
- Given 已 `login_user(alice_id)` 且会话有效 When 会话保持期内再次访问受保护路由 Then 放行无需重复登录；`logout_user()` 后再访问 Then 回到 302 拦截（需重新登录）。

## 8. 独立验证方式

- 建议测试：`tests/test_fp003_auth.py`——哈希/校验往返与盐随机性；未登录拦截 302；登录后放行；登出后再拦截。
- 验证命令：`python3 -m pytest tests/test_fp003_auth.py -q`
