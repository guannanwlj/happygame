# FP-002 Web 服务与应用骨架 — 设计说明

> 依据：`input/tasks/social-platform/FP-002-web-skeleton.task.md`（唯一实现依据）。
> 技术栈：Python 3.12 + Flask + SQLite + pytest（本任务不触数据库）。

## 目标

交付 Flask 应用工厂（`create_app`）与统一页面骨架（布局 + 导航 + 首页 + 模板继承体系），
为 FP-004~FP-011 的全部功能页面提供挂载点。

## 结构

```
social_app/
├── __init__.py          # create_app / register_blueprints（契约源）
└── templates/
    ├── base.html        # 布局 + 顶栏导航 + flash 消息区 + title/content 两块
    └── index.html       # 首页欢迎与导航说明（继承 base.html）
tests/test_fp002_skeleton.py
requirements.txt         # 声明 flask（pytest 由 CI 安装，见下）
```

## 关键决策

1. **应用工厂严格按 §3.2 契约实现**：`create_app()` 内部 `Flask(__name__)`、
   `app.secret_key = os.environ.get("SOCIAL_SECRET_KEY", "dev-secret")`、注册 `GET /`
   首页、末尾调用 `register_blueprints(app)` 后返回。
2. **`register_blueprints` 是注册表而非通用 API**：函数体为空注册表，
   各功能任务合入时逐行追加 `app.register_blueprint(<模块>.bp)`（源码注释标明追加位置）。
   测试按 §6 在测试内注册示例蓝图（`/__dummy__`）验证挂载机制，不依赖任何功能任务。
3. **导航硬编码 href**：`base.html` 顶栏以字面 `href` 输出路由规划表的全部**固定路径**
   （`/`、`/register`、`/login`、`/logout`、`/friends/requests`、`/friends`、`/posts/new`、`/feed`），
   不用 `url_for`（页面未实现时 `url_for` 会构建成功但点击 404，与硬编码行为一致且断言稳定）。
4. **变量路径不进顶栏**：`/friends/requests/<int:req_id>/accept|reject` 含 int 转换器，
   无法作为字面 href 输出；按 INTEGRATION.md I-17，其入口由 FP-007 待处理列表页按请求 id
   寻址（列表页按钮），故顶栏不包含这两条。首页导航说明中列出全部规划路径作为总账。
5. **模板继承**：`base.html` 只定义 `{% block title %}` 与 `{% block content %}` 两个块
   （外加 flash 消息区），功能页模板 `{% extends "base.html" %}` 填充即可，骨架不预设更多块。
6. **不预设登录态/数据库**：无 `before_request` 拦截（FP-003）、无存储（FP-001）。
7. **依赖声明**：新增 `requirements.txt`（flask）。CI 的 flask 安装适配归 FP-012（E-06），
   本任务不改 `ci.yml`，避免越界。
8. **不做“未挂载路径 404”的硬断言**：该状态是暂时性的（FP-004+ 合入后即变），
   固化会导致后续任务“回归性破坏”，故验收聚焦持久契约：首页渲染、导航链接、
   挂载机制、模板继承、密钥覆盖。

## 验证

`python3 -m pytest tests/test_fp002_skeleton.py -q`；全量 `python3 -m pytest`。
