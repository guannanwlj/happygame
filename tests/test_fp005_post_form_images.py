"""FP-005 tests: post-form image picker (social_app.views_post template).

Scenarios documented in docs/test-cases/fp005-post-form-images.md. Card §6
seed strategy: every test gets a fresh temporary database (SOCIAL_DB) with a
seeded ``users`` row and drives requests through the real ``create_app()``
registry with a real ``session.create_session`` token — no guard stubbing.
The §7 rejection scenario monkeypatches ``social_app.posts.create_post`` to
raise ``PostError`` and posts a urlencoded body the existing handler parses.
"""

import pytest

from social_app import db, posts, session
from social_app.app import Request, create_app


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so tests never touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    db.init_db()
    yield str(path)


@pytest.fixture(autouse=True)
def clean_sessions():
    """Isolate every test from the process-wide session store (FP-003)."""
    with session._lock:
        session._sessions.clear()
    yield
    with session._lock:
        session._sessions.clear()


@pytest.fixture
def app():
    """The real route registry: GET /posts/new and POST /posts mounted."""
    return create_app()


@pytest.fixture
def login_token():
    """Card §6 seed: one real user row plus a session token for it."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("fp005-user", "hash"),
    )
    return session.create_session(cur.lastrowid)


def request(method="GET", path="/posts/new", body=b"", token=None):
    """Card §6 request: real Request dataclass, session cookie when given."""
    cookies = {session.SESSION_COOKIE: token} if token else {}
    return Request(method=method, path=path, body=body, cookies=cookies)


def reject_create_post(monkeypatch, reason="图片数量不能超过 9 张"):
    """Card §7: simulate any service-layer rejection through PostError."""

    def boom(author_id, content):
        raise posts.PostError(reason)

    monkeypatch.setattr(posts, "create_post", boom)


def get_form(app, token):
    """Dispatch the logged-in GET /posts/new."""
    return app.dispatch(request(token=token))


def submit(app, token, body):
    """Dispatch a logged-in urlencoded POST /posts."""
    return app.dispatch(
        request(method="POST", path="/posts", body=body, token=token)
    )


class TestAcceptance:
    """A1–A4: the card §7 acceptance criteria."""

    def test_form_is_multipart_with_multi_file_input(self, app, login_token):
        body = get_form(app, login_token).body
        assert 'enctype="multipart/form-data"' in body
        assert 'type="file"' in body
        assert 'id="images"' in body
        assert 'name="images"' in body
        assert "multiple" in body
        assert (
            'accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,'
            'image/webp"' in body
        )

    def test_rejection_rerenders_error_and_keeps_content(
        self, app, login_token, monkeypatch
    ):
        reject_create_post(monkeypatch)
        response = submit(app, login_token, b"content=hello")
        assert response.status == 200
        assert "Location" not in response.headers
        assert '<p class="error">图片数量不能超过 9 张</p>' in response.body
        assert ">hello</textarea>" in response.body

    def test_anonymous_get_redirects_to_login(self, app):
        response = app.dispatch(request())
        assert response.status == 303
        assert response.headers["Location"] == "/login"
        assert "<form" not in response.body

    def test_existing_form_elements_preserved(self, app, login_token):
        body = get_form(app, login_token).body
        assert "<textarea" in body
        assert 'name="content"' in body
        assert 'action="/posts"' in body
        assert 'method="post"' in body
        assert '<button type="submit">发布</button>' in body


class TestPickerMarkup:
    """A3 + B3: the picker is labelled and survives a re-render."""

    def test_picker_has_label(self, app, login_token):
        body = get_form(app, login_token).body
        assert '<label for="images">图片</label>' in body

    def test_rejection_keeps_multipart_form_and_picker(
        self, app, login_token, monkeypatch
    ):
        reject_create_post(monkeypatch)
        body = submit(app, login_token, b"content=hello").body
        assert 'enctype="multipart/form-data"' in body
        assert 'name="images"' in body


class TestRefillEscaping:
    """E1: the retained refill mechanism still escapes echoed content."""

    def test_rejected_content_is_escaped(self, app, login_token, monkeypatch):
        reject_create_post(monkeypatch)
        body = submit(app, login_token, b"content=%3Cscript%3E").body
        assert "&lt;script&gt;</textarea>" in body
        assert "<script>" not in body
