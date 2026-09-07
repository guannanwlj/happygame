# FP-002 Web 服务与应用骨架 — 测试场景

> 对应任务卡 §7 验收标准与 §8 独立验证方式。落位：`tests/test_fp002_skeleton.py`。

## 场景总表（GWT）

### S1 首页渲染（§7 用例 1）

- **S1.1 主路径**：Given `create_app()` 已调用，When 测试客户端 GET `/`，
  Then 返回 200 且 Content-Type 为 text/html，页面含完整布局
  （`<!DOCTYPE html>`、`<nav>` 顶栏、欢迎语「欢迎」、导航说明）。
- **S1.2 导航总账**：Given 首页响应，Then 顶栏含路由规划表全部固定路径的链接
  `href="..."`：`/`、`/register`、`/login`、`/logout`、`/friends/requests`、
  `/friends`、`/posts/new`、`/feed`（参数化逐条断言）。
- **S1.3 变量路径说明**：含 `<int:req_id>` 的接受/拒绝路由无法字面输出，
  由 FP-007 列表页按 id 寻址（设计决策 4），不在顶栏断言范围。

### S2 蓝图挂载点（§7 用例 2 / §6 Mock 策略）

- **S2.1 示例蓝图**：Given 测试内定义 `bp = Blueprint("dummy", __name__)`
  并挂路由 `GET /__dummy__`，When 在 `create_app()` 产出的 app 上
  `app.register_blueprint(bp)` 后访问，Then 返回 200 且内容正确
  （证明后续功能页挂载机制可用，不依赖任何功能任务）。
- **S2.2 工厂调用注册表**：Given 对 `social_app.register_blueprints` 打桩记录调用，
  When 调用 `create_app()`，Then 注册表以该 app 为参被调用（契约「末尾调用」）。

### S3 模板继承（§7 用例 3）

- **S3.1 子模板填充两块**：Given 字符串子模板 `{% extends "base.html" %}`
  并覆写 `title`/`content` 两块，When 渲染，Then `<title>` 含子模板标题、
  正文含子模板内容，且继承出顶栏导航与布局。
- **S3.2 flash 消息区**：Given 请求上下文中 `flash("...")`，
  When 渲染继承 base 的模板，Then 消息以列表项出现在页面（flash 区可用）。

### S4 会话密钥（§8）

- **S4.1 环境变量覆盖**：Given 设置 `SOCIAL_SECRET_KEY=test-secret-...`，
  When `create_app()`，Then `app.secret_key` 等于该值。
- **S4.2 缺省值**：Given 未设置该环境变量，When `create_app()`，
  Then `app.secret_key == "dev-secret"`（开发常量）。

### S5 边界与非范围

- **S5.1**：`create_app()` 每次返回新的 Flask 实例（无全局单例污染）。
- **S5.2**：骨架自身不触数据库、不做登录拦截（非范围 §5），不设相关断言；
  未挂载路径当前 404 属暂时状态（设计决策 8），不固化为断言。

## 验证命令

- 单文件：`python3 -m pytest tests/test_fp002_skeleton.py -q`
- 全量：`python3 -m pytest`
