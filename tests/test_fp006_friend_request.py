"""FP-006 tests: send friend request (social_app/friends_request.py).

Scenarios documented in docs/test-cases/fp006-send-friend-request.md.
FP-002/FP-003 are not merged yet, so per task card §6 every test mounts the
blueprint on a minimal self-built Flask shell and injects the login state
directly via session_transaction(). FP-001 storage is real (merged).
"""

from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask

from social_app import db
from social_app.friends_request import bp


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Fresh initialized DB per test via $SOCIAL_DB (never touches the repo)."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    db.init_db()
    yield str(path)


@pytest.fixture()
def app() -> Flask:
    """Minimal self-built Flask shell (FP-002 skeleton not merged, card §6)."""
    application = Flask(__name__)
    application.secret_key = "test-secret"
    application.register_blueprint(bp)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(username: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, "h1"),
    )
    return cur.lastrowid


def make_friendship(a: int, b: int) -> None:
    """Seed a bidirectional friendship pair (FP-001 convention: two rows)."""
    db.execute("INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (a, b))
    db.execute("INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (b, a))


def make_request(requester_id: int, addressee_id: int, status: str = "pending") -> int:
    cur = db.execute(
        "INSERT INTO friend_requests (requester_id, addressee_id, status)"
        " VALUES (?, ?, ?)",
        (requester_id, addressee_id, status),
    )
    return cur.lastrowid


def pair_requests(a: int, b: int) -> list:
    """All friend_request rows between a and b in either direction."""
    return db.query_all(
        "SELECT * FROM friend_requests"
        " WHERE (requester_id = ? AND addressee_id = ?)"
        "    OR (requester_id = ? AND addressee_id = ?)",
        (a, b, b, a),
    )


def pending_between(a: int, b: int) -> list:
    return [r for r in pair_requests(a, b) if r["status"] == "pending"]


def login(client, user_id: int) -> None:
    """Inject the login state directly (FP-003 not merged, card §6)."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def post_request(client, username: str):
    return client.post("/friends/requests", data={"username": username})


@pytest.fixture()
def users():
    """Card §6 seed users; relational pre-states are composed per test."""
    return {"alice": make_user("alice"), "bob": make_user("bob"), "carol": make_user("carol")}


class TestAcceptance:
    """Card §7: the five GWT acceptance scenarios."""

    def test_a1_success_creates_pending_request(self, client, users):
        login(client, users["alice"])

        resp = post_request(client, "bob")

        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == "好友请求已发送"
        rows = pending_between(users["alice"], users["bob"])
        assert len(rows) == 1
        assert rows[0]["requester_id"] == users["alice"]
        assert rows[0]["addressee_id"] == users["bob"]
        assert rows[0]["status"] == "pending"

    def test_a2_unknown_username_creates_nothing(self, client, users):
        login(client, users["alice"])

        resp = post_request(client, "ghost")

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "用户不存在"
        assert pair_requests(users["alice"], users["bob"]) == []

    def test_a3_cannot_add_self(self, client, users):
        login(client, users["alice"])

        resp = post_request(client, "alice")

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "不能加自己"
        assert pair_requests(users["alice"], users["alice"]) == []

    def test_a4_already_friends_blocked(self, client, users):
        make_friendship(users["alice"], users["carol"])  # §6 seed: alice–carol
        login(client, users["alice"])

        resp = post_request(client, "carol")

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "已是好友"
        assert pair_requests(users["alice"], users["carol"]) == []

    def test_a5_duplicate_pending_keeps_single_row(self, client, users):
        make_request(users["alice"], users["bob"])  # existing pending
        login(client, users["alice"])

        resp = post_request(client, "bob")

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "已有待处理请求"
        assert len(pending_between(users["alice"], users["bob"])) == 1

    def test_a6_rejected_history_allows_resend(self, client, users):
        make_request(users["alice"], users["bob"], status="rejected")
        login(client, users["alice"])

        resp = post_request(client, "bob")

        assert resp.status_code == 200
        rows = pair_requests(users["alice"], users["bob"])
        assert len(rows) == 2  # old rejected preserved + new pending
        assert sorted(r["status"] for r in rows) == ["pending", "rejected"]
        new = [r for r in rows if r["status"] == "pending"][0]
        assert new["requester_id"] == users["alice"]
        assert new["addressee_id"] == users["bob"]


class TestValidationEdges:
    """Card §4 equivalent-implementation edges."""

    def test_b1_reverse_pending_blocks(self, client, users):
        make_request(users["bob"], users["alice"])  # §6 seed: bob→alice pending
        login(client, users["alice"])

        resp = post_request(client, "bob")

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "已有待处理请求"
        assert len(pair_requests(users["alice"], users["bob"])) == 1  # only the seed

    def test_b2_friendship_checked_in_both_directions(self, client, users):
        make_friendship(users["alice"], users["carol"])
        login(client, users["carol"])

        resp = post_request(client, "alice")

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "已是好友"
        assert pair_requests(users["alice"], users["carol"]) == []

    def test_b3_missing_username_field(self, client, users):
        login(client, users["alice"])

        resp = client.post("/friends/requests", data={})

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "用户不存在"
        assert pair_requests(users["alice"], users["bob"]) == []

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_b4_blank_username(self, client, users, raw):
        login(client, users["alice"])

        resp = post_request(client, raw)

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "用户不存在"
        assert pair_requests(users["alice"], users["bob"]) == []

    def test_b5_surrounding_whitespace_is_stripped(self, client, users):
        login(client, users["alice"])

        resp = post_request(client, " bob ")

        assert resp.status_code == 200
        assert len(pending_between(users["alice"], users["bob"])) == 1

    def test_b6_username_match_is_exact_case_sensitive(self, client, users):
        login(client, users["alice"])

        resp = post_request(client, "Bob")

        assert resp.status_code == 400
        assert resp.get_data(as_text=True) == "用户不存在"
        assert pair_requests(users["alice"], users["bob"]) == []


class TestAuthAndRouting:
    """Card §3.2 mounting contract: login gate and POST-only route."""

    def test_c1_unauthenticated_redirects_to_login(self, client, users):
        resp = post_request(client, "bob")

        assert resp.status_code == 302
        location = urlparse(resp.headers["Location"])
        assert location.path == "/login"
        assert parse_qs(location.query).get("next") == ["/friends/requests"]
        assert pair_requests(users["alice"], users["bob"]) == []

    def test_c2_get_not_allowed(self, client):
        resp = client.get("/friends/requests")
        assert resp.status_code == 405


class TestStateMachine:
    """Card §3.1 state machine: history never blocks a fresh request."""

    def test_d1_rejected_and_pending_coexist_after_resend(self, client, users):
        rejected_id = make_request(users["alice"], users["bob"], status="rejected")
        login(client, users["alice"])

        assert post_request(client, "bob").status_code == 200

        by_id = {r["id"]: r for r in pair_requests(users["alice"], users["bob"])}
        assert by_id[rejected_id]["status"] == "rejected"  # untouched
        assert len(by_id) == 2

    def test_d2_accepted_history_does_not_block_new_request(self, client, users):
        make_request(users["alice"], users["bob"], status="accepted")
        login(client, users["alice"])

        resp = post_request(client, "bob")

        assert resp.status_code == 200
        assert len(pending_between(users["alice"], users["bob"])) == 1
