"""Local startup entrypoint for the social platform (FP-004).

``python -m social_app`` idempotently initializes the SQLite schema via
``social_app.db.init_db()`` and then serves the Flask application on the
loopback interface with the built-in single-process development server.
The database file is controlled by the SOCIAL_DB environment variable
(read at call time, see ``social_app/db.py``); the listen port can be
overridden with SOCIAL_PORT (default 5000).
"""

import os

from social_app import db

DEFAULT_PORT = 5000
PORT_ENV = "SOCIAL_PORT"


def _port() -> int:
    return int(os.environ.get(PORT_ENV, DEFAULT_PORT))


def _placeholder_create_app():
    """Minimal factory used until FP-001's real create_app is merged."""
    from flask import Flask

    app = Flask(__name__)

    @app.route("/")
    def index():
        return "social_app development placeholder (FP-001 pending)"

    return app


def _load_create_app():
    """Return FP-001's app factory, falling back per task card §6."""
    try:
        from social_app.app import create_app
    except ImportError:
        return _placeholder_create_app
    return create_app


def main() -> None:
    db.init_db()
    app = _load_create_app()()
    app.run(host="127.0.0.1", port=_port(), use_reloader=False)


if __name__ == "__main__":
    main()
