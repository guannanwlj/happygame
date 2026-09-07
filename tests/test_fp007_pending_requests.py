"""FP-007 tests: pending friend request list (social_app/pending_requests.py).

Scenarios documented in docs/test-cases/fp007-pending-request-list.md.
FP-002/FP-003/FP-006 are not merged yet, so per the task-card Mock strategy
(§6 style) every test uses the minimal self-built app shell, seeds
friend_requests rows directly through FP-001 storage, and injects the login
state via session_transaction(). FP-001 storage is real (merged).
"""

from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask

from social_app import create_app, db

EMPTY_STATE_TEXT = "暂无待处理请求"
PAGE_TITLE = "待处理好友请求"


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


def make_request(
    requester_id: int,
    addressee_id: int,
    status: str = "pending",
    created_at: str = "2026-01-01T00:00:00.000Z",
) -> int:
    cur = db.execute(
        "INSERT INTO friend_requests (requester_id, addressee_id, status, created_at)"
        " VALUES (?, ?, ?, ?)",
        (requester_id, addressee_id, status, created_at),
    )
    return cur.lastrowid


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
    """S1–S6: the list-page contract."""

    def test_s1_lists_pending_incoming_requests(self, client, users):
        make_request(users["bob"], users["alice"], created_at="2026-01-02T00:00:00.000Z")
        make_request(users["carol"], users["alice"], created_at="2026-01-03T00:00:00.000Z")
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "bob" in text
        assert "carol" in text
        assert "2026-01-02T00:00:00.000Z" in text
        assert "2026-01-03T00:00:00.000Z" in text

    def test_s2_only_incoming_direction_listed(self, client, users):
        make_request(users["bob"], users["alice"])  # incoming
        make_request(users["alice"], users["carol"])  # sent by alice
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "bob" in text
        assert "carol" not in text

    def test_s3_only_pending_status_listed(self, client, users):
        make_request(users["bob"], users["alice"], status="pending")
        make_request(users["carol"], users["alice"], status="rejected")
        make_request(users["dave"], users["alice"], status="accepted")
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "bob" in text
        assert "carol" not in text
        assert "dave" not in text

    def test_s4_newest_first_ordering(self, client, users):
        make_request(users["bob"], users["alice"], created_at="2026-01-01T08:00:00.000Z")
        make_request(users["carol"], users["alice"], created_at="2026-01-03T08:00:00.000Z")
        make_request(users["dave"], users["alice"], created_at="2026-01-02T08:00:00.000Z")
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        text = resp.get_data(as_text=True)
        order = [text.find(name) for name in ("carol", "dave", "bob")]
        assert -1 not in order
        assert order == sorted(order)  # newest first

    def test_s5_rows_address_accept_reject_by_request_id(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert f'href="/friends/requests/{rid}/accept"' in text
        assert f'href="/friends/requests/{rid}/reject"' in text
        assert "接受" in text
        assert "拒绝" in text

    def test_s6_empty_state(self, client, users):
        make_request(users["alice"], users["bob"])  # someone else's queue
        make_request(users["carol"], users["alice"], status="rejected")
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert EMPTY_STATE_TEXT in text
        assert "/accept" not in text
        assert "/reject" not in text


class TestAuthAndPageContract:
    """S7–S10: login gate, page skeleton, escaping, stale session."""

    def test_s7_unauthenticated_redirected_to_login(self, client, users):
        resp = client.get("/friends/requests")

        assert resp.status_code == 302
        location = urlparse(resp.headers["Location"])
        assert location.path == "/login"
        assert parse_qs(location.query).get("next") == ["/friends/requests"]

    def test_s8_page_extends_base_skeleton(self, client, users):
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")
        text = resp.get_data(as_text=True)
        assert f"<title>{PAGE_TITLE}</title>" in text
        assert "<html" in text
        assert PAGE_TITLE in text  # page heading fills the content block

    def test_s9_username_html_escaped(self, client, users):
        evil_id = make_user("<b>evil</b>")
        make_request(evil_id, users["alice"])
        login(client, users["alice"])

        resp = client.get("/friends/requests")

        text = resp.get_data(as_text=True)
        assert "<b>evil</b>" not in text
        assert "&lt;b&gt;evil&lt;/b&gt;" in text

    def test_s10_stale_session_renders_empty_state(self, client, users):
        login(client, 424242)  # no such users row

        resp = client.get("/friends/requests")

        assert resp.status_code == 200
        assert EMPTY_STATE_TEXT in resp.get_data(as_text=True)
