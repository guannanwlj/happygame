"""Flask web layer for the social platform (FP-001 web skeleton).

Application factory + feature-blueprint auto-registration. Every later
feature task delivers ``social_app/web/<name>.py`` with a module-level
``bp = Blueprint("<name>", __name__)`` (templates under
``social_app/web/templates/<name>/``) and mounts it either by appending the
name to ``FEATURES`` or by passing ``create_app(features=(...))`` explicitly.
"""

import os
from collections.abc import Iterable
from importlib import import_module

from flask import Flask, render_template

#: Feature modules registered by ``create_app()`` by default. Append a name
#: here (one-line change) to mount ``social_app/web/<name>.py``.
FEATURES: tuple[str, ...] = ("home",)

SECRET_KEY_ENV = "SOCIAL_SECRET_KEY"
DEFAULT_SECRET_KEY = "dev-secret-key"


def _load_feature(name):
    """Import ``social_app.web.<name>`` and return it, failing clearly."""
    dotted = f"social_app.web.{name}"
    try:
        module = import_module(dotted)
    except ImportError as exc:
        raise ImportError(
            f"未知的功能模块 {dotted!r}：请确认 social_app/web/{name}.py 存在，"
            f"或检查 FEATURES / create_app(features=...) 配置"
        ) from exc
    if not hasattr(module, "bp"):
        raise ImportError(
            f"功能模块 {dotted!r} 缺少模块级 bp（Blueprint）："
            f"请定义 bp = Blueprint({name!r}, __name__)"
        )
    return module


def create_app(features: Iterable[str] | None = None) -> Flask:
    """Create the Flask app, register feature blueprints and error pages."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(SECRET_KEY_ENV, DEFAULT_SECRET_KEY)

    for name in FEATURES if features is None else features:
        app.register_blueprint(_load_feature(name).bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500

    return app
