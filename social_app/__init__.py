"""FP-002 Web 服务与应用骨架。

对外提供骨架契约（任务卡 §3.2，后续功能任务按此挂载）：

- ``create_app()``：Flask 应用工厂（secret_key、``GET /`` 首页、蓝图注册表）；
- ``register_blueprints(app)``：蓝图注册表，各功能任务在此逐行追加。
"""

import os

from flask import Flask, render_template


def create_app() -> Flask:
    """应用工厂：构建 Flask 实例、签名密钥、基座路由与蓝图挂载点。"""
    app = Flask(__name__)
    app.secret_key = os.environ.get("SOCIAL_SECRET_KEY", "dev-secret")

    @app.get("/")
    def index():
        return render_template("index.html")

    register_blueprints(app)
    return app


def register_blueprints(app: Flask) -> None:
    """蓝图注册表：各功能任务在此追加一行 ``app.register_blueprint(<模块>.bp)``。

    对应模块未合入时该行不存在；后续任务合并时逐行追加并解冲突。
    """
    # 蓝图约定：每个功能模块文件定义 ``bp = Blueprint("<蓝图名>", __name__)``，
    # 例如（FP-004 合入后）：
    #     from . import register
    #     app.register_blueprint(register.bp)
