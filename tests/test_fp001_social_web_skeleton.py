"""FP-001 tests: social platform web app skeleton (social_app package).

Scenarios documented in docs/test-cases/fp001-social-web-skeleton.md. Per
card §6 no mock framework is used: a real ThreadingHTTPServer runs on a
random free port in a daemon thread and every request goes through stdlib
urllib.request.
"""

import contextlib
import threading
import urllib.error
import urllib.request

import pytest

from social_app.app import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HOST_ENV,
    PORT_ENV,
    Request,
    Response,
    Route,
    bind_address,
    create_app,
    create_server,
    parse_form,
    redirect,
    render_page,
)

TEST_HOST = "127.0.0.1"


def http(method: str, url: str, body: bytes | None = None, headers: dict | None = None):
    """Send one HTTP request; return (status, headers, decoded body).

    HTTPError is captured so 4xx/5xx responses are inspectable like 2xx.
    """
    request = urllib.request.Request(
        url, data=body, method=method, headers=headers or {}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read().decode("utf-8")


@contextlib.contextmanager
def serving(app):
    """Serve `app` on a random free port; yield its base URL."""
    server = create_server(app, host=TEST_HOST, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{TEST_HOST}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def base_url():
    """Base URL of a default skeleton app running on a random port."""
    with serving(create_app()) as url:
        yield url


class TestHomePage:
    """A1, A2: GET / renders the feed placeholder."""

    def test_root_renders_feed_placeholder(self, base_url):
        status, headers, body = http("GET", base_url + "/")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")
        assert "<!DOCTYPE html>" in body
        assert "占位" in body

    def test_root_links_to_login_and_register(self, base_url):
        _, _, body = http("GET", base_url + "/")
        assert 'href="/login"' in body
        assert 'href="/register"' in body

    def test_root_ignores_query_string(self, base_url):
        status, _, body = http("GET", base_url + "/?debug=1")
        assert status == 200
        assert "占位" in body


class TestHealthz:
    """A3: health check."""

    def test_healthz_returns_ok(self, base_url):
        status, headers, body = http("GET", base_url + "/healthz")
        assert status == 200
        assert body == "ok"
        assert headers["Content-Type"].startswith("text/plain")


class TestRouterBehavior:
    """B1–B3: unmatched paths and wrong methods."""

    def test_unknown_path_returns_404(self, base_url):
        status, _, _ = http("GET", base_url + "/no-such-path")
        assert status == 404

    def test_post_root_returns_405_with_allow(self, base_url):
        status, headers, _ = http("POST", base_url + "/")
        assert status == 405
        assert "GET" in headers["Allow"]

    def test_get_posts_returns_405_with_allow(self, base_url):
        status, headers, _ = http("GET", base_url + "/posts")
        assert status == 405
        assert "POST" in headers["Allow"]


class TestSkeletonNotImplemented:
    """C1–C5: 501 mount points naming the task that will mount them.

    Login / logout were mounted by FP-008 (see
    ``tests/test_fp008_login_page.py``), so they are no longer placeholders.
    """

    @pytest.mark.parametrize(
        "method,path,mounting_task",
        [
            ("GET", "/posts/new", "FP-012"),
            ("POST", "/posts", "FP-012"),
        ],
    )
    def test_placeholder_returns_501(self, base_url, method, path, mounting_task):
        status, _, body = http(method, base_url + path, body=b"x=1")
        assert status == 501
        assert "501" in body
        assert mounting_task in body

    def test_login_routes_are_mounted_not_placeholders(self, base_url):
        for method, path in (("GET", "/login"), ("POST", "/login"), ("POST", "/logout")):
            status, _, body = http(method, base_url + path, body=b"x=1")
            assert status != 501
            assert "FP-008" not in body


class TestRouteRegistryExtensibility:
    """D1–D3: later tasks mount handlers through the same registry."""

    def test_reregistration_replaces_skeleton_handler(self):
        app = create_app()
        app.route("POST", "/register", lambda req: Response(body="mounted"))
        with serving(app) as url:
            status, _, body = http("POST", url + "/register", body=b"x=1")
        assert status == 200
        assert body == "mounted"

    def test_new_route_with_param_served(self):
        app = create_app()

        def extra(request: Request) -> Response:
            return Response(body=f"extra:{request.params['name']}")

        app.route("GET", "/extras/<name>", extra)
        with serving(app) as url:
            status, _, body = http("GET", url + "/extras/hike")
        assert status == 200
        assert body == "extra:hike"

    def test_registry_contains_all_skeleton_routes(self):
        routes = {(route.method, route.pattern) for route in create_app().routes}
        assert routes >= {
            ("GET", "/"),
            ("GET", "/healthz"),
            ("GET", "/register"),
            ("POST", "/register"),
            ("GET", "/login"),
            ("POST", "/login"),
            ("POST", "/logout"),
            ("GET", "/posts/new"),
            ("POST", "/posts"),
            ("POST", "/follow"),
        }

    def test_register_routes_are_mounted_over_placeholders(self):
        from social_app.views_register import register_page, register_submit

        routes = {
            (route.method, route.pattern): route.handler
            for route in create_app().routes
        }
        assert routes[("GET", "/register")] is register_page
        assert routes[("POST", "/register")] is register_submit


class TestPathParamsAndHelpers:
    """E1–E6: param matching boundary + rendering/form/redirect helpers."""

    def test_extra_path_segment_returns_404(self, base_url):
        status, _, _ = http("GET", base_url + "/posts/1/extra")
        assert status == 404

    def test_route_param_matches_single_segment(self):
        route = Route("GET", "/posts/<id>", lambda req: Response())
        assert route.match("/posts/1") == {"id": "1"}

    def test_route_param_does_not_cross_slashes(self):
        route = Route("GET", "/posts/<id>", lambda req: Response())
        assert route.match("/posts/1/extra") is None

    def test_render_page_escapes_title(self):
        page = render_page("<script>", "<p>body</p>")
        assert "&lt;script&gt;" in page
        assert "<script>" not in page

    def test_parse_form_decodes_single_values(self):
        assert parse_form(b"username=a+b&password=p%40ss&empty=") == {
            "username": "a b",
            "password": "p@ss",
            "empty": "",
        }

    def test_parse_form_empty_body(self):
        assert parse_form(b"") == {}

    def test_redirect_sets_location_and_303(self):
        response = redirect("/login")
        assert response.status == 303
        assert response.headers == {"Location": "/login"}


class TestCookies:
    """F1–F3: Cookie header parsing into Request.cookies."""

    @contextlib.contextmanager
    def whoami_app(self):
        app = create_app()
        app.route(
            "GET",
            "/whoami",
            lambda req: Response(body=repr(req.cookies)),
        )
        with serving(app) as url:
            yield url

    def test_cookie_header_parsed(self):
        with self.whoami_app() as url:
            status, _, body = http(
                "GET", url + "/whoami", headers={"Cookie": "session=abc"}
            )
        assert status == 200
        assert body == repr({"session": "abc"})

    def test_multiple_cookies_parsed(self):
        with self.whoami_app() as url:
            _, _, body = http(
                "GET", url + "/whoami", headers={"Cookie": "session=abc; theme=dark"}
            )
        assert body == repr({"session": "abc", "theme": "dark"})

    def test_no_cookie_header_is_empty(self):
        with self.whoami_app() as url:
            _, _, body = http("GET", url + "/whoami")
        assert body == repr({})


class TestBindAddress:
    """G1–G3: SOCIAL_HOST / SOCIAL_PORT resolution shared with __main__."""

    def test_defaults_when_env_unset(self, monkeypatch):
        monkeypatch.delenv(HOST_ENV, raising=False)
        monkeypatch.delenv(PORT_ENV, raising=False)
        assert bind_address() == (DEFAULT_HOST, DEFAULT_PORT)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv(HOST_ENV, "0.0.0.0")
        monkeypatch.setenv(PORT_ENV, "9001")
        assert bind_address() == ("0.0.0.0", 9001)

    def test_invalid_port_raises_with_env_name(self, monkeypatch):
        monkeypatch.setenv(PORT_ENV, "http")
        with pytest.raises(ValueError, match=PORT_ENV):
            bind_address()


class TestServerFactory:
    """G4: factory binds a real random port (application instantiable)."""

    def test_random_port_bound_and_serving(self):
        with serving(create_app()) as url:
            status, _, body = http("GET", url + "/healthz")
        assert status == 200
        assert body == "ok"
