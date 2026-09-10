"""Social platform web application package (FP-001 web app skeleton).

Stdlib-only base: a route registry, request/response objects and
server-side rendered placeholders that the later social features (FP-006
register page, FP-008 login/logout, FP-010 follow UI, FP-012 post UI,
FP-014 feed) mount onto. See `social_app.app` for the routing/rendering
core and `social_app.__main__` for the startup entry point.
"""

from social_app.app import (
    SocialApp,
    Request,
    Response,
    bind_address,
    create_app,
    create_server,
)

__all__ = [
    "SocialApp",
    "Request",
    "Response",
    "bind_address",
    "create_app",
    "create_server",
]
