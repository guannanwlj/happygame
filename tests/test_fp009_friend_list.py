"""FP-009 tests: my friend list (social_app/friends.py).

Scenarios documented in docs/test-cases/fp009-friend-list.md.
FP-002/FP-003/FP-008 are not merged yet, so per the task-card Mock strategy
(§6 style) every test uses the minimal self-built app shell, seeds the
symmetric friendships row pairs (exactly what FP-008's accept writes)
directly through FP-001 storage, and injects the login state via
session_transaction(). FP-001 storage is real (merged).
"""

from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask

from social_app import create_app, db

EMPTY_STATE_TEXT = "暂无好友"
PAGE_TITLE = "我的好友"


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Fresh initialized DB per test via $SOCIAL_DB (never touches the repo)."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    db.init_db()
    yield str(path)


@pytest.fixture()
def app() -> Flask:
    """Minimal self-built Flask shell (FP-002 skeleton not merged)."""
    return create_app()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(username: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, "h1"),
    )
    return cur.lastrowid


def befriend(a: int, b: int, created_at: str = "2026-01-01T00:00:00.000Z") -> None:
    """Seed the symmetric pair FP-008's accept writes, at a fixed time."""
    with db.transaction() as conn:
        for user_id, friend_id in ((a, b), (b, a)):
            conn.execute(
                "INSERT INTO friendships (user_id, friend_id, created_at)"
                " VALUES (?, ?, ?)",
                (user_id, friend_id, created_at),
            )


def login(client, user_id: int) -> None:
    """Inject the login state directly (FP-003 not merged)."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


@pytest.fixture()
def users():
    """Seed users (§6 style); relational pre-states are composed per test."""
    return {
        "alice": make_user("alice"),
        "bob": make_user("bob"),
        "carol": make_user("carol"),
        "dave": make_user("dave"),
    }


class TestAcceptance:
    """S1–S5: the list-page contract."""

    def test_s1_lists_own_friends_with_since_time(self, client, users):
        befriend(users["alice"], users["bob"], created_at="2026-01-02T00:00:00.000Z")
        befriend(users["alice"], users["carol"], created_at="2026-01-03T00:00:00.000Z")
        login(client, users["alice"])

        resp = client.get("/friends")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "bob" in text
        assert "carol" in text
        assert "2026-01-02T00:00:00.000Z" in text
        assert "2026-01-03T00:00:00.000Z" in text

    def test_s2_symmetric_storage_rendered_once(self, client, users):
        befriend(users["alice"], users["bob"])
        login(client, users["alice"])

        resp = client.get("/friends")

        text = resp.get_data(as_text=True)
        assert text.count("bob") == 1

    def test_s3_only_own_friends_visible_both_sides(self, client, users):
        befriend(users["alice"], users["bob"])
        befriend(users["bob"], users["carol"])

        login(client, users["alice"])
        alice_text = client.get("/friends").get_data(as_text=True)
        assert "bob" in alice_text
        assert "carol" not in alice_text

        login(client, users["carol"])
        carol_text = client.get("/friends").get_data(as_text=True)
        assert "bob" in carol_text
        assert "alice" not in carol_text

    def test_s4_newest_first_ordering(self, client, users):
        befriend(users["alice"], users["bob"], created_at="2026-01-01T08:00:00.000Z")
        befriend(users["alice"], users["carol"], created_at="2026-01-03T08:00:00.000Z")
        befriend(users["alice"], users["dave"], created_at="2026-01-02T08:00:00.000Z")
        login(client, users["alice"])

        resp = client.get("/friends")

        text = resp.get_data(as_text=True)
        order = [text.find(name) for name in ("carol", "dave", "bob")]
        assert -1 not in order
        assert order == sorted(order)  # newest first

    def test_s5_empty_state(self, client, users):
        befriend(users["bob"], users["carol"])  # someone else's friendship
        login(client, users["alice"])

        resp = client.get("/friends")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert EMPTY_STATE_TEXT in text
        assert "bob" not in text


class TestAuthAndPageContract:
    """S6–S9: login gate, page skeleton, escaping, stale session."""

    def test_s6_unauthenticated_redirected_to_login(self, client, users):
        resp = client.get("/friends")

        assert resp.status_code == 302
        location = urlparse(resp.headers["Location"])
        assert location.path == "/login"
        assert parse_qs(location.query).get("next") == ["/friends"]

    def test_s7_page_extends_base_skeleton(self, client, users):
        login(client, users["alice"])

        resp = client.get("/friends")

        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")
        text = resp.get_data(as_text=True)
        assert f"<title>{PAGE_TITLE}</title>" in text
        assert "<html" in text
        assert PAGE_TITLE in text  # page heading fills the content block

    def test_s8_username_html_escaped(self, client, users):
        evil_id = make_user("<b>evil</b>")
        befriend(users["alice"], evil_id)
        login(client, users["alice"])

        resp = client.get("/friends")

        text = resp.get_data(as_text=True)
        assert "<b>evil</b>" not in text
        assert "&lt;b&gt;evil&lt;/b&gt;" in text

    def test_s9_stale_session_renders_empty_state(self, client, users):
        login(client, 424242)  # no such users row

        resp = client.get("/friends")

        assert resp.status_code == 200
        assert EMPTY_STATE_TEXT in resp.get_data(as_text=True)


class TestRouteContract:
    """S10–S11: read-only mounting and data invariance."""

    def test_s10_get_only_post_rejected(self, client, users):
        login(client, users["alice"])

        assert client.get("/friends").status_code == 200
        assert client.post("/friends").status_code == 405

    def test_s11_view_writes_nothing(self, client, users):
        befriend(users["alice"], users["bob"])
        befriend(users["alice"], users["carol"])
        login(client, users["alice"])
        before = [tuple(r) for r in db.query_all("SELECT * FROM friendships ORDER BY id")]

        resp = client.get("/friends")

        assert resp.status_code == 200
        after = [tuple(r) for r in db.query_all("SELECT * FROM friendships ORDER BY id")]
        assert after == before
