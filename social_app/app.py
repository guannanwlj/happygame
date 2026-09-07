"""Flask application factory & common page frame (FP-001).

Provides the web-layer skeleton every later page task hooks into: the
``create_app()`` factory, the optional feature-blueprint mounting, the root
redirect and the 404 error page. Storage stays in :mod:`social_app.db`
(untouched here); no authentication happens in the skeleton (FP-003).
"""

import importlib
import os
from pathlib import Path

from flask import Flask, redirect, render_template

SECRET_KEY_ENV = "SOCIAL_SECRET_KEY"
DEFAULT_SECRET_KEY = "dev-secret"

#: Repo-root ``templates/`` (the card's canonical template location, one
#: level above this package).
TEMPLATE_FOLDER = Path(__file__).resolve().parent.parent / "templates"

#: Feature blueprints mounted when present: ``(module name, attribute)``.
#: Missing modules or attributes are skipped so the skeleton starts while
#: the other feature tasks are unimplemented.
BLUEPRINTS = [
    ("social_app.auth", "bp"),
    ("social_app.friends", "bp"),
    ("social_app.feed", "bp"),
]


def register_optional_blueprints(app: Flask) -> None:
    """Register every feature blueprint that currently exists."""
    for module_name, attribute in BLUEPRINTS:
        try:
            module = importlib.import_module(module_name)
            blueprint = getattr(module, attribute)
        except (ImportError, AttributeError):
            continue
        app.register_blueprint(blueprint)


def create_app() -> Flask:
    """Build the Flask app: session key, 404 page, root redirect, blueprints."""
    app = Flask(__name__, template_folder=str(TEMPLATE_FOLDER))
    app.secret_key = os.environ.get(SECRET_KEY_ENV, DEFAULT_SECRET_KEY)

    @app.route("/")
    def index():
        return redirect("/feed")

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    register_optional_blueprints(app)
    return app
