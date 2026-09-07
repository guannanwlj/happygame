"""Minimal Flask application shell for FP-011 (self-built per task card §6).

FP-002 owns the real skeleton; until it merges, this factory does only what
the friends feed needs: a session secret, schema init (idempotent), and
mounting the feed blueprint.
"""

import os

from flask import Flask

from social_app import db
from social_app.feed import bp as feed_bp


def create_app() -> Flask:
    """Build the Flask app and mount the feed blueprint."""
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-fp011")
    db.init_db()
    app.register_blueprint(feed_bp)
    return app
