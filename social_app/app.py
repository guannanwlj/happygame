"""Flask application factory (embedded FP-002 stand-in for FP-003).

FP-002 (app wiring) is not merged yet, so FP-003 self-builds the minimal
factory contract it needs: create_app() initializes the schema, applies
configuration, mounts the auth blueprint, and normalizes every error response
to JSON (HTTP errors included, AuthError subclasses mapped to status codes).
"""

import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from social_app import db
from social_app.auth import (
    InvalidCredentialsError,
    UsernameTakenError,
    ValidationError,
)
from social_app.routes import auth_bp

SECRET_KEY_ENV = "SOCIAL_APP_SECRET_KEY"
DEV_SECRET_KEY = "dev-insecure-secret-key-change-me"


def create_app(config: dict | None = None) -> Flask:
    """Build a configured Flask app (schema initialized, auth mounted)."""
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get(SECRET_KEY_ENV, DEV_SECRET_KEY))
    if config:
        app.config.update(config)

    db.init_db()
    app.register_blueprint(auth_bp)

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify({"error": exc.description}), exc.code

    @app.errorhandler(ValidationError)
    def validation_error(exc):
        return jsonify({"error": str(exc)}), 400

    @app.errorhandler(UsernameTakenError)
    def username_taken(exc):
        return jsonify({"error": str(exc)}), 409

    @app.errorhandler(InvalidCredentialsError)
    def invalid_credentials(exc):
        return jsonify({"error": str(exc)}), 401

    return app
