"""Minimal Flask application shell (FP-002 stand-in per FP-005 card §6).

The real FP-002 skeleton is not merged yet; this factory mounts the login
blueprint so FP-005 is independently runnable and testable. FP-002's full
factory (base template, error pages, all blueprints) replaces this module.
"""

import os

from flask import Flask

from social_app import db
from social_app.login import bp as login_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SOCIAL_SECRET_KEY", "dev-secret-key")
    db.init_db()  # idempotent; schema from FP-001
    app.register_blueprint(login_bp)

    @app.get("/")
    def index():
        return "社交平台首页"

    return app
