"""Web application skeleton for the social platform (FP-001).

Stdlib-only stack: `ThreadingHTTPServer` + `BaseHTTPRequestHandler` with a
「path pattern → handler」 route registry and server-rendered HTML string
templates. Every later social feature (FP-006 register page, FP-008 login /
logout, FP-010 follow UI, FP-012 post UI, FP-014 feed) mounts real handlers
onto the same registry; until then the mount points answer 501 with a note
naming the mounting task. Request cookies are parsed from the `Cookie` header
so FP-003 can build session handling on top.
"""

import html
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HOST_ENV = "SOCIAL_HOST"
PORT_ENV = "SOCIAL_PORT"
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
    cookies: dict[str, str] = field(default_factory=dict)


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


def redirect(location: str, status: int = 303) -> Response:
    """A redirect response; 303 See Other is the default (POST → GET)."""
    return Response(status=status, headers={"Location": location})


def parse_form(body: bytes) -> dict[str, str]:
    """Decode an urlencoded form body into a single-value field dict.

    Repeated names keep their first value; blank fields are preserved.
    """
    fields = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {name: values[0] for name, values in fields.items()}


# --------------------------------------------------------------------------- #
# Skeleton handlers (card §3.2). Real handlers are mounted over these.
# --------------------------------------------------------------------------- #


def home_page(_request: Request) -> Response:
    """GET / — feed placeholder; FP-014 mounts the real feed here."""
    body = (
        '<section id="feed" class="placeholder">\n'
        "  <p>首页 / 帖流占位：真帖流由后续功能（FP-014）挂载。</p>\n"
        '  <nav><a href="/login">登录</a> · <a href="/register">注册</a></nav>\n'
        "</section>"
    )
    return html_response("社交平台", body)


def healthz(_request: Request) -> Response:
    """GET /healthz — liveness probe."""
    return text_response("ok")


def not_implemented(feature: str, mounting_task: str) -> Handler:
    """Build a 501 placeholder handler naming the task that will mount it."""

    def placeholder(_request: Request) -> Response:
        return text_response(
            f"501 Not Implemented：{feature}由后续功能（{mounting_task}）挂载。",
            status=501,
        )

    return placeholder


# --------------------------------------------------------------------------- #
# Routing: an ordered registry of Route entries + a dispatcher.
# --------------------------------------------------------------------------- #

_PLACEHOLDER_RE = re.compile(r"<([^<>]+)>")


class Route:
    """One registered route: method + pattern with `<param>` segments.

    A `<param>` segment matches one path segment (`[^/]+`), e.g. the pattern
    `/posts/<id>` matches `/posts/1` with `params == {"id": "1"}` but does
    not match `/posts/1/extra`.
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


class SocialApp:
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


def parse_cookies(header: str) -> dict[str, str]:
    """Parse a `Cookie` header (`a=1; b=2`) into a flat single-value dict."""
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        name, sep, value = part.partition("=")
        if sep and name.strip():
            cookies[name.strip()] = value.strip()
    return cookies


def make_handler(app: SocialApp) -> type[BaseHTTPRequestHandler]:
    """Build a request-handler class bound to `app` (dispatches to it)."""

    class SocialRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "SocialApp/0.1"

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
                body=self._read_body(),
                cookies=parse_cookies(self.headers.get("Cookie", "")),
            )
            self._write(app.dispatch(request))

        def _read_body(self) -> bytes:
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

    return SocialRequestHandler


def bind_address(env: Mapping[str, str] | None = None) -> tuple[str, int]:
    """Resolve (host, port) from SOCIAL_HOST / SOCIAL_PORT at call time."""
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


def create_app() -> SocialApp:
    """Build the skeleton app with every card §3.2 mount point registered."""
    app = SocialApp()
    app.route("GET", "/", home_page)
    app.route("GET", "/healthz", healthz)
    app.route("GET", "/register", not_implemented("注册页面", "FP-006"))
    app.route("POST", "/register", not_implemented("注册页面", "FP-006"))
    app.route("GET", "/login", not_implemented("登录与退出", "FP-008"))
    app.route("POST", "/login", not_implemented("登录与退出", "FP-008"))
    app.route("POST", "/logout", not_implemented("登录与退出", "FP-008"))
    app.route("GET", "/posts/new", not_implemented("发帖界面", "FP-012"))
    app.route("POST", "/posts", not_implemented("发帖界面", "FP-012"))
    app.route("POST", "/follow", not_implemented("关注操作界面", "FP-010"))
    return app


def create_server(
    app: SocialApp | None = None,
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
