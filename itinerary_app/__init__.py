"""Itinerary planner web application package (FP-001 web app skeleton).

Stdlib-only base: a route registry + server-side rendered placeholders that
the later itinerary features (FP-005 form, FP-009 generation, FP-011 result
page, FP-012 Markdown export) mount onto. See `itinerary_app.app` for the
routing/rendering core and `itinerary_app.__main__` for the startup entry.
The FP-002 LLM channel lives in `itinerary_app.llm`.
"""

from itinerary_app.app import (
    ItineraryApp,
    Request,
    Response,
    bind_address,
    create_app,
    create_server,
)

__all__ = [
    "ItineraryApp",
    "Request",
    "Response",
    "bind_address",
    "create_app",
    "create_server",
]
