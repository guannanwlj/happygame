"""Social platform application package.

Minimal Flask shell following the FP-002 mounting contract (task card FP-010
§6: FP-002 未合入 → 自建最小 Flask 壳挂载本蓝图). FP-002's merge extends
`create_app` (home route, layout/nav) and appends blueprint lines in
`register_blueprints`.
"""

import os

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Blueprint registry: each feature task appends its `app.register_blueprint`."""
    from social_app import posts

    app.register_blueprint(posts.bp)


def create_app() -> Flask:
    """Application factory: secret key, blueprint mounting."""
    app = Flask(__name__)
    app.secret_key = os.environ.get("SOCIAL_SECRET_KEY", "dev-secret")
    register_blueprints(app)
    return app
