"""Web application skeleton for the itinerary planner (FP-001).

Stdlib-only stack: `ThreadingHTTPServer` + `BaseHTTPRequestHandler` with a
「path pattern → handler」 route registry and server-rendered HTML string
templates. The five S6 routes are registered as skeleton placeholders; the
business features mount real handlers onto the same registry in later task
cards (FP-005 / FP-009 / FP-011 / FP-012). Until then the generate/export
routes answer 501 with a note naming the mounting task.
"""

import html
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HOST_ENV = "ITIN_HOST"
PORT_ENV = "ITIN_PORT"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

HTML_CONTENT_TYPE = "text/html; charset=utf-8"
TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"


# --------------------------------------------------------------------------- #
# Request / response objects passed between the router and handlers.
# --------------------------------------------------------------------------- #


@dataclass
class Request:
    """One dispatched HTTP request (path params filled in by the router)."""

    method: str
    path: str
    params: dict[str, str] = field(default_factory=dict)
    query: dict[str, list[str]] = field(default_factory=dict)
    body: bytes = b""


@dataclass
class Response:
    """One HTTP response; `body` is text, encoded as UTF-8 on the wire."""

    status: int = 200
    body: str = ""
    content_type: str = HTML_CONTENT_TYPE
    headers: dict[str, str] = field(default_factory=dict)


Handler = Callable[[Request], Response]


# --------------------------------------------------------------------------- #
# Server-side rendering: string templates, no template library.
# --------------------------------------------------------------------------- #

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
</head>
<body>
<header><h1>{title}</h1></header>
<main>
{body}
</main>
</body>
</html>
"""


def render_page(title: str, body_html: str) -> str:
    """Wrap a title + body fragment into the shared HTML page skeleton."""
    return PAGE_TEMPLATE.format(title=html.escape(title), body=body_html)


def html_response(title: str, body_html: str, status: int = 200) -> Response:
    return Response(status=status, body=render_page(title, body_html))


def text_response(
    body: str, status: int = 200, headers: dict[str, str] | None = None
) -> Response:
    return Response(
        status=status,
        body=body,
        content_type=TEXT_CONTENT_TYPE,
        headers=headers or {},
    )


# --------------------------------------------------------------------------- #
# Skeleton handlers for the five S6 routes (card §3.2).
# --------------------------------------------------------------------------- #


def form_page(_request: Request) -> Response:
    """GET / — form page placeholder; the real form mounts in FP-005."""
    body = (
        '<section id="itinerary-form" class="placeholder">\n'
        "  <p>行程条件与偏好输入表单占位：真表单由后续功能（FP-005）挂载。</p>\n"
        "</section>"
    )
    return html_response("行程规划", body)


def healthz(_request: Request) -> Response:
    """GET /healthz — liveness probe."""
    return text_response("ok")


def itinerary_page(request: Request) -> Response:
    """GET /itinerary/<id> — result page placeholder with guidance copy."""
    itinerary_id = html.escape(request.params.get("id", ""))
    body = (
        '<section id="itinerary-result" class="placeholder">\n'
        f"  <p>行程编号：{itinerary_id}</p>\n"
        '  <p>暂无行程：请返回<a href="/">首页</a>填写行程条件并提交生成。</p>\n'
        "</section>"
    )
    return html_response("行程结果", body)


def generate_placeholder(_request: Request) -> Response:
    """POST /generate — 501 mount point; the flow mounts in FP-009."""
    return text_response(
        "501 Not Implemented：行程生成由后续功能（FP-009）挂载。", status=501
    )


def export_placeholder(_request: Request) -> Response:
    """GET /itinerary/<id>/export.md — 501 mount point; FP-012 mounts here."""
    return text_response(
        "501 Not Implemented：Markdown 导出由后续功能（FP-012）挂载。", status=501
    )


# --------------------------------------------------------------------------- #
# Routing: an ordered registry of Route entries + a dispatcher.
# --------------------------------------------------------------------------- #

_PLACEHOLDER_RE = re.compile(r"<([^<>]+)>")


class Route:
    """One registered route: method + pattern with `<param>` segments.

    A `<param>` segment matches one path segment (`[^/]+`), e.g. the pattern
    `/itinerary/<id>` matches `/itinerary/abc` with `params == {"id": "abc"}`.
    """

    def __init__(self, method: str, pattern: str, handler: Handler) -> None:
        self.method = method.upper()
        self.pattern = pattern
        self.handler = handler
        self._regex = self._compile(pattern)

    @staticmethod
    def _compile(pattern: str) -> re.Pattern[str]:
        parts: list[str] = []
        pos = 0
        for match in _PLACEHOLDER_RE.finditer(pattern):
            parts.append(re.escape(pattern[pos : match.start()]))
            parts.append(f"(?P<{match.group(1)}>[^/]+)")
            pos = match.end()
        parts.append(re.escape(pattern[pos:]))
        return re.compile("^" + "".join(parts) + "$")

    def match(self, path: str) -> dict[str, str] | None:
        """Return path params if `path` matches this route's pattern."""
        found = self._regex.match(path)
        return found.groupdict() if found else None


class ItineraryApp:
    """Instantiable application: an extensible route registry + dispatcher."""

    def __init__(self) -> None:
        self._routes: list[Route] = []

    @property
    def routes(self) -> tuple[Route, ...]:
        return tuple(self._routes)

    def route(self, method: str, pattern: str, handler: Handler) -> Handler:
        """Register `handler` for `method pattern`; return the handler.

        Registering the same (method, pattern) again replaces the earlier
        entry, so later tasks can mount real handlers over skeleton ones.
        """
        method = method.upper()
        self._routes = [
            route
            for route in self._routes
            if not (route.method == method and route.pattern == pattern)
        ]
        self._routes.append(Route(method, pattern, handler))
        return handler

    def dispatch(self, request: Request) -> Response:
        """Match `request` against the registry and run the handler."""
        method = request.method.upper()
        path_matches: list[tuple[Route, dict[str, str]]] = []
        for route in self._routes:
            params = route.match(request.path)
            if params is None:
                continue
            path_matches.append((route, params))
            if route.method == method:
                request.params = params
                return route.handler(request)
        if not path_matches:
            return text_response("404 Not Found", status=404)
        allowed = ", ".join(sorted({route.method for route, _ in path_matches}))
        return text_response(
            "405 Method Not Allowed", status=405, headers={"Allow": allowed}
        )


# --------------------------------------------------------------------------- #
# HTTP server wiring: handler class factory + server factory.
# --------------------------------------------------------------------------- #


def make_handler(app: ItineraryApp) -> type[BaseHTTPRequestHandler]:
    """Build a request-handler class bound to `app` (dispatches to it)."""

    class ItineraryRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "ItineraryApp/0.1"

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802 (http.server API)
            self._dispatch("POST")

        def _dispatch(self, method: str) -> None:
            split = urlsplit(self.path)
            request = Request(
                method=method,
                path=split.path,
                query=parse_qs(split.query),
                body=self._read_body(method),
            )
            self._write(app.dispatch(request))

        def _read_body(self, method: str) -> bytes:
            if method != "POST":
                return b""
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length > 0 else b""

        def _write(self, response: Response) -> None:
            payload = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # keep dev-server / pytest output quiet

    return ItineraryRequestHandler


def bind_address(env: Mapping[str, str] | None = None) -> tuple[str, int]:
    """Resolve (host, port) from ITIN_HOST / ITIN_PORT at call time."""
    source = os.environ if env is None else env
    host = source.get(HOST_ENV, DEFAULT_HOST)
    raw_port = source.get(PORT_ENV, str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(
            f"{PORT_ENV} must be an integer port, got {raw_port!r}"
        ) from exc
    return host, port


def create_app() -> ItineraryApp:
    """Build the skeleton app with the five S6 routes registered."""
    app = ItineraryApp()
    app.route("GET", "/", form_page)
    app.route("GET", "/healthz", healthz)
    app.route("POST", "/generate", generate_placeholder)
    app.route("GET", "/itinerary/<id>", itinerary_page)
    app.route("GET", "/itinerary/<id>/export.md", export_placeholder)
    return app


def create_server(
    app: ItineraryApp | None = None,
    host: str | None = None,
    port: int | None = None,
) -> ThreadingHTTPServer:
    """Bind a ThreadingHTTPServer for `app` (defaults: fresh app + env)."""
    if app is None:
        app = create_app()
    if host is None or port is None:
        env_host, env_port = bind_address()
        host = host if host is not None else env_host
        port = port if port is not None else env_port
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    return server
