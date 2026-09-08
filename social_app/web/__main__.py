"""Dev-server entry point: ``python3 -m social_app.web``."""

import os

from social_app.web import create_app

DEBUG_ENV = "SOCIAL_DEBUG"
_TRUTHY = {"1", "true", "on"}


def main() -> None:
    app = create_app()
    debug = os.environ.get(DEBUG_ENV, "").strip().lower() in _TRUTHY
    app.run(host="127.0.0.1", port=5000, debug=debug)


if __name__ == "__main__":
    main()
