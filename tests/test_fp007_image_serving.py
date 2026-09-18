"""FP-007 (image serving) tests: GET /images/<storage_name>.

Scenarios documented in docs/test-cases/fp007-image-serving.md. In-process
dispatch (``create_app().dispatch`` / direct handler calls) covers the guard,
name whitelist and 404 paths; one class drives a real ThreadingHTTPServer via
``http.client`` for the wire-level binary-body / Content-Length checks (card
§7 acceptance 4+5). Per card §6 the FP-003 writer is never invoked: the image
directory is a temp dir seeded with files written directly, and the login
state is a seed user in a temp SOCIAL_DB plus a real session token.
"""

import contextlib
import http.client
import threading

import pytest

from social_app import db, session, views_image
from social_app.app import (
    Request,
    SocialApp,
    create_app,
    create_server,
    redirect,
)

TEST_HOST = "127.0.0.1"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + bytes(range(256))
JPEG_BYTES = b"\xff\xd8\xff\xe0JFIF" + b"jpeg-body\x00" * 7
WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 " + b"webp-body"

# name → (on-disk payload, expected Content-Type)
SEEDS = {
    "seed.png": (PNG_BYTES, "image/png"),
    "seed.jpg": (JPEG_BYTES, "image/jpeg"),
    "seed.jpeg": (JPEG_BYTES, "image/jpeg"),
    "seed.webp": (WEBP_BYTES, "image/webp"),
}


@pytest.fixture(autouse=True)
def clean_sessions():
    """Isolate every test from the process-wide session store (FP-003)."""
    with session._lock:
        session._sessions.clear()
    yield
    with session._lock:
        session._sessions.clear()


@pytest.fixture
def image_dir(tmp_path, monkeypatch):
    """Card §6 seed strategy: empty temp dir announced via $SOCIAL_IMAGE_DIR."""
    directory = tmp_path / "imgs"
    directory.mkdir()
    monkeypatch.setenv(views_image.IMAGE_DIR_ENV, str(directory))
    return directory


@pytest.fixture
def seed_user(tmp_path, monkeypatch):
    """One user in a temp database; sessions are created from its id."""
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "social.db"))
    with contextlib.closing(db.get_connection()) as conn:
        db.init_db(conn)
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES ('fp007', 'x')"
        )
        return cursor.lastrowid


@pytest.fixture
def login_cookie(seed_user):
    """Cookie dict of a real FP-003 session for the seed user."""
    token = session.create_session(seed_user)
    return {session.SESSION_COOKIE: token}


def image_request(name, cookies=None):
    return Request(
        method="GET", path=f"/images/{name}", cookies=cookies or {}
    )


def handler_request(name, cookies=None):
    """Request aimed straight at the handler with a crafted path param."""
    request = image_request(name, cookies)
    request.params = {"name": name}
    return request


@contextlib.contextmanager
def serving():
    """Serve a full ``create_app()`` on a free port; yield that port."""
    server = create_server(create_app(), host=TEST_HOST, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def fetch(port, path, cookies=None):
    """One raw GET over the wire; return (status, headers, body bytes)."""
    headers = {
        "Cookie": "; ".join(f"{k}={v}" for k, v in (cookies or {}).items())
    }
    conn = http.client.HTTPConnection(TEST_HOST, port, timeout=5)
    conn.request("GET", path, headers=headers)
    response = conn.getresponse()
    result = (response.status, dict(response.getheaders()), response.read())
    conn.close()
    return result


class TestLoggedInServing:
    """A1–A4: seeded files stream back byte-identical with mapped types."""

    @pytest.mark.parametrize("filename", sorted(SEEDS))
    def test_bytes_and_content_type(
        self, image_dir, login_cookie, filename
    ):
        payload, content_type = SEEDS[filename]
        (image_dir / filename).write_bytes(payload)
        response = create_app().dispatch(image_request(filename, login_cookie))
        assert response.status == 200
        assert isinstance(response.body, bytes)
        assert response.body == payload
        assert response.content_type == content_type

    def test_body_matches_disk_exactly(self, image_dir, login_cookie):
        payload = PNG_BYTES + b"\x00\xff" * 9
        (image_dir / "seed.png").write_bytes(payload)
        response = create_app().dispatch(image_request("seed.png", login_cookie))
        assert response.body == (image_dir / "seed.png").read_bytes()


class TestAnonymous:
    """B1–B2: the login guard runs before any file access (D-6)."""

    def test_redirects_to_login(self, image_dir):
        (image_dir / "seed.png").write_bytes(PNG_BYTES)
        response = create_app().dispatch(image_request("seed.png"))
        assert response.status == 303
        assert response.headers["Location"] == "/login"

    def test_guard_response_returned_unchanged(
        self, image_dir, monkeypatch
    ):
        guard = redirect("/login")
        monkeypatch.setattr(
            views_image, "require_login", lambda request: guard
        )
        assert views_image.serve_image(handler_request("seed.png")) is guard


class TestMissingFile:
    """C1–C2: unknown storage names 404 without leaking the layout."""

    def test_missing_file_is_404(self, image_dir, login_cookie):
        response = create_app().dispatch(image_request("nope.png", login_cookie))
        assert response.status == 404

    def test_404_does_not_leak_disk_paths(self, image_dir, login_cookie):
        response = create_app().dispatch(image_request("nope.png", login_cookie))
        assert isinstance(response.body, str)
        assert "uploads" not in response.body
        assert str(image_dir.parent) not in response.body


class TestIllegalNames:
    """D1–D6: the whole-string whitelist is the only way to a file."""

    @pytest.mark.parametrize(
        "name",
        [
            "seed.PNG",  # uppercase extension
            "seed.gif",  # extension outside the whitelist
            "seed%2Epng",  # percent-encoded dot
            "..%2Fseed.png",  # encoded traversal
            "no-extension",
            "seed..png",
            "seed.png\n",  # fullmatch, not ^…$ + match
            ".png",  # empty token
        ],
    )
    def test_non_whitelisted_name_is_404(self, image_dir, login_cookie, name):
        response = create_app().dispatch(image_request(name, login_cookie))
        assert response.status == 404

    def test_multi_segment_path_is_404(self, image_dir, login_cookie):
        response = create_app().dispatch(
            image_request("../outside.png", login_cookie)
        )
        assert response.status == 404

    def test_traversal_never_reads_outside_file(
        self, image_dir, login_cookie, tmp_path
    ):
        outside = tmp_path / "outside.png"  # sibling of the image dir
        outside.write_bytes(PNG_BYTES)
        response = views_image.serve_image(
            handler_request("../outside.png", login_cookie)
        )
        assert response.status == 404
        assert response.body != PNG_BYTES

    def test_uppercase_extension_even_when_file_exists(
        self, image_dir, login_cookie
    ):
        (image_dir / "seed.PNG").write_bytes(PNG_BYTES)
        response = create_app().dispatch(image_request("seed.PNG", login_cookie))
        assert response.status == 404


class TestRouteWiring:
    """E1–E4: mounting and the storage-directory contract."""

    def test_create_app_registers_route(self):
        routes = create_app().routes
        assert ("GET", "/images/<name>") in [
            (route.method, route.pattern) for route in routes
        ]

    def test_register_on_bare_app(self, image_dir, login_cookie):
        app = SocialApp()
        views_image.register(app)
        (image_dir / "seed.png").write_bytes(PNG_BYTES)
        response = app.dispatch(image_request("seed.png", login_cookie))
        assert response.status == 200
        assert response.body == PNG_BYTES

    def test_post_is_method_not_allowed(self, login_cookie):
        response = create_app().dispatch(
            Request(
                method="POST",
                path="/images/seed.png",
                cookies=login_cookie,
            )
        )
        assert response.status == 405
        assert "GET" in response.headers["Allow"]

    def test_image_dir_resolves_env_at_call_time(self, monkeypatch, tmp_path):
        assert views_image.image_dir() == views_image.DEFAULT_IMAGE_DIR
        monkeypatch.setenv(views_image.IMAGE_DIR_ENV, str(tmp_path))
        assert views_image.image_dir() == str(tmp_path)


class TestWireOutput:
    """F1–F4: real server, http.client — bytes on the wire + regression."""

    def test_binary_body_over_the_wire(
        self, image_dir, seed_user, login_cookie
    ):
        (image_dir / "seed.png").write_bytes(PNG_BYTES)
        with serving() as port:
            status, headers, body = fetch(
                port, "/images/seed.png", login_cookie
            )
        assert status == 200
        assert body == PNG_BYTES
        assert headers["Content-Type"] == "image/png"
        assert int(headers["Content-Length"]) == len(PNG_BYTES)

    def test_text_endpoints_unchanged(
        self, image_dir, seed_user, login_cookie
    ):
        with serving() as port:
            feed_status, feed_headers, feed_body = fetch(
                port, "/", login_cookie
            )
            health_status, health_headers, health_body = fetch(
                port, "/healthz"
            )
        assert feed_status == 200
        assert feed_headers["Content-Type"].startswith("text/html")
        assert b"<!DOCTYPE html>" in feed_body
        assert int(feed_headers["Content-Length"]) == len(feed_body)
        assert health_status == 200
        assert health_body == b"ok"
        assert health_headers["Content-Type"].startswith("text/plain")
        assert int(health_headers["Content-Length"]) == len(b"ok")

    def test_anonymous_over_the_wire(self, image_dir):
        (image_dir / "seed.png").write_bytes(PNG_BYTES)
        with serving() as port:
            status, headers, _ = fetch(port, "/images/seed.png")
        assert status == 303
        assert headers["Location"] == "/login"
