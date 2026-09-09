"""FP-001 tests: itinerary web app skeleton (itinerary_app package).

Scenarios documented in docs/test-cases/fp001-web-skeleton.md. Per card §6
no mock framework is used: a real ThreadingHTTPServer runs on a random free
port in a daemon thread and every request goes through stdlib
urllib.request.
"""

import contextlib
import threading
import urllib.error
import urllib.request

import pytest

from itinerary_app.app import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HOST_ENV,
    PORT_ENV,
    Request,
    Response,
    bind_address,
    create_app,
    create_server,
)

TEST_HOST = "127.0.0.1"


def http(method: str, url: str, body: bytes | None = None):
    """Send one HTTP request; return (status, headers, decoded body).

    HTTPError is captured so 4xx/5xx responses are inspectable like 2xx.
    """
    request = urllib.request.Request(url, data=body, method=method)
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


class TestFormPage:
    """A1, B1: GET / renders the form-page placeholder."""

    def test_root_renders_form_placeholder(self, base_url):
        status, headers, body = http("GET", base_url + "/")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")
        assert "行程规划" in body
        assert "占位" in body

    def test_root_ignores_query_string(self, base_url):
        status, _, body = http("GET", base_url + "/?debug=1")
        assert status == 200
        assert "行程规划" in body


class TestHealthz:
    """A2: health check."""

    def test_healthz_returns_ok(self, base_url):
        status, headers, body = http("GET", base_url + "/healthz")
        assert status == 200
        assert body == "ok"
        assert headers["Content-Type"].startswith("text/plain")


class TestResultPage:
    """A3, D1, D2: GET /itinerary/<id> placeholder / guidance state."""

    def test_result_page_placeholder_guidance(self, base_url):
        status, headers, body = http("GET", base_url + "/itinerary/abc")
        assert status == 200
        assert headers["Content-Type"].startswith("text/html")
        assert "暂无行程" in body

    def test_result_page_links_back_to_form(self, base_url):
        _, _, body = http("GET", base_url + "/itinerary/abc")
        assert 'href="/"' in body

    def test_result_page_escapes_itinerary_id(self):
        response = create_app().dispatch(
            Request(method="GET", path="/itinerary/<script>")
        )
        assert response.status == 200
        assert "&lt;script&gt;" in response.body
        assert "<script>" not in response.body


class TestSkeletonNotImplemented:
    """A4, A5: 501 mount points for FP-009 / FP-012."""

    def test_post_generate_returns_501(self, base_url):
        status, _, body = http(
            "POST", base_url + "/generate", body=b"origin=x&days=3"
        )
        assert status == 501
        assert "501" in body

    def test_get_export_md_returns_501(self, base_url):
        status, _, body = http("GET", base_url + "/itinerary/abc/export.md")
        assert status == 501
        assert "501" in body


class TestRouterBehavior:
    """B2–B5: unmatched paths and wrong methods."""

    def test_unknown_path_returns_404(self, base_url):
        status, _, _ = http("GET", base_url + "/no-such-path")
        assert status == 404

    def test_wrong_method_returns_405_with_allow(self, base_url):
        status, headers, _ = http("GET", base_url + "/generate")
        assert status == 405
        assert "POST" in headers["Allow"]

    def test_post_root_returns_405_with_allow(self, base_url):
        status, headers, _ = http("POST", base_url + "/")
        assert status == 405
        assert "GET" in headers["Allow"]

    def test_param_does_not_cross_slashes(self, base_url):
        status, _, _ = http("GET", base_url + "/itinerary/abc/extra")
        assert status == 404


class TestRouteRegistryExtensibility:
    """C1–C3: later tasks mount handlers through the same registry."""

    def test_new_route_with_param_served(self):
        app = create_app()

        def extra(request: Request) -> Response:
            return Response(body=f"extra:{request.params['name']}")

        app.route("GET", "/extras/<name>", extra)
        with serving(app) as url:
            status, _, body = http("GET", url + "/extras/hike")
        assert status == 200
        assert body == "extra:hike"

    def test_reregistration_replaces_skeleton_handler(self):
        app = create_app()
        app.route("POST", "/generate", lambda req: Response(body="mounted"))
        with serving(app) as url:
            status, _, body = http("POST", url + "/generate")
        assert status == 200
        assert body == "mounted"

    def test_registry_contains_all_s6_routes(self):
        routes = {(route.method, route.pattern) for route in create_app().routes}
        assert routes >= {
            ("GET", "/"),
            ("GET", "/healthz"),
            ("POST", "/generate"),
            ("GET", "/itinerary/<id>"),
            ("GET", "/itinerary/<id>/export.md"),
        }


class TestBindAddress:
    """E1–E3: ITIN_HOST / ITIN_PORT resolution shared with __main__."""

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
    """E4: factory binds a real random port (application instantiable)."""

    def test_random_port_bound_and_serving(self):
        with serving(create_app()) as url:
            status, _, body = http("GET", url + "/healthz")
        assert status == 200
        assert body == "ok"
