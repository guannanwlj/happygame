"""FP-008 tests: accept/reject friend request (social_app/friend_request_actions.py).

Scenarios documented in docs/test-cases/fp008-accept-reject-request.md.
FP-002/FP-003/FP-006/FP-007 are not merged yet, so per the task-card Mock
strategy (§6 style) every test uses the minimal self-built app shell
(create_app from social_app/__init__.py), seeds rows directly through the
FP-001 storage API, and injects the login state via session_transaction().
Redirects are asserted by Location header only — the target page belongs to
FP-007. FP-001 storage is real (merged).
"""

from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask

from social_app import create_app, db

MSG_ACCEPTED = "好友请求已接受"
MSG_REJECTED = "好友请求已拒绝"
OLD_TS = "2020-01-01T00:00:00.000Z"  # explicit seed timestamp ≠ any "now"


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Fresh initialized DB per test via $SOCIAL_DB (never touches the repo)."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    db.init_db()
    yield str(path)


@pytest.fixture()
def app() -> Flask:
    """App from the minimal self-built shell (FP-002 skeleton not merged)."""
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
    created_at: str = OLD_TS,
) -> int:
    cur = db.execute(
        "INSERT INTO friend_requests"
        " (requester_id, addressee_id, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (requester_id, addressee_id, status, created_at, created_at),
    )
    return cur.lastrowid


def make_friendship(a: int, b: int) -> None:
    db.execute("INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (a, b))


def request_row(request_id: int):
    return db.query_one("SELECT * FROM friend_requests WHERE id = ?", (request_id,))


def friendship_rows() -> list:
    return db.query_all("SELECT user_id, friend_id FROM friendships ORDER BY user_id")


def flashed(client) -> list:
    """Flash messages carried in the session (rendered by FP-007 after merge)."""
    with client.session_transaction() as sess:
        return [message for _category, message in sess.get("_flashes", [])]


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


def accept(client, request_id: int, method: str = "get"):
    url = f"/friends/requests/{request_id}/accept"
    return getattr(client, method)(url)


def reject(client, request_id: int, method: str = "get"):
    url = f"/friends/requests/{request_id}/reject"
    return getattr(client, method)(url)


class TestAcceptance:
    """A1–A4: the two main paths, GET and POST twins."""

    def test_a1_accept_marks_accepted_and_creates_both_friendship_rows(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["alice"])

        resp = accept(client, rid)

        assert resp.status_code == 303
        assert resp.headers["Location"] == "/friends/requests"
        assert flashed(client) == [MSG_ACCEPTED]
        row = request_row(rid)
        assert row["status"] == "accepted"
        assert row["updated_at"] != OLD_TS  # refreshed on the transition
        assert [(r["user_id"], r["friend_id"]) for r in friendship_rows()] == [
            (users["alice"], users["bob"]),
            (users["bob"], users["alice"]),
        ]

    def test_a2_reject_marks_rejected_and_writes_no_friendships(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["alice"])

        resp = reject(client, rid)

        assert resp.status_code == 303
        assert resp.headers["Location"] == "/friends/requests"
        assert flashed(client) == [MSG_REJECTED]
        row = request_row(rid)
        assert row["status"] == "rejected"
        assert row["updated_at"] != OLD_TS
        assert friendship_rows() == []

    def test_a3_accept_via_post_matches_get(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["alice"])

        resp = accept(client, rid, method="post")

        assert resp.status_code == 303
        assert flashed(client) == [MSG_ACCEPTED]
        assert request_row(rid)["status"] == "accepted"
        assert len(friendship_rows()) == 2

    def test_a4_reject_via_post_matches_get(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["alice"])

        resp = reject(client, rid, method="post")

        assert resp.status_code == 303
        assert flashed(client) == [MSG_REJECTED]
        assert request_row(rid)["status"] == "rejected"
        assert friendship_rows() == []


class TestAuthorization:
    """B1–B5: only the addressee of a pending row may act."""

    def test_b1_requester_cannot_accept_own_outgoing_request(self, client, users):
        rid = make_request(users["alice"], users["bob"])  # alice → bob
        login(client, users["alice"])  # alice is the requester here

        resp = accept(client, rid)

        assert resp.status_code == 404
        assert request_row(rid)["status"] == "pending"
        assert friendship_rows() == []

    def test_b2_third_party_cannot_act(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["carol"])

        assert accept(client, rid).status_code == 404
        assert reject(client, rid).status_code == 404

        assert request_row(rid)["status"] == "pending"
        assert friendship_rows() == []

    def test_b3_anonymous_accept_redirects_to_login(self, client, users):
        rid = make_request(users["bob"], users["alice"])

        resp = accept(client, rid)

        assert resp.status_code == 302
        location = urlparse(resp.headers["Location"])
        assert location.path == "/login"
        assert parse_qs(location.query).get("next") == [
            f"/friends/requests/{rid}/accept"
        ]
        assert request_row(rid)["status"] == "pending"
        assert friendship_rows() == []

    def test_b4_anonymous_reject_redirects_to_login(self, client, users):
        rid = make_request(users["bob"], users["alice"])

        resp = reject(client, rid)

        assert resp.status_code == 302
        location = urlparse(resp.headers["Location"])
        assert parse_qs(location.query).get("next") == [
            f"/friends/requests/{rid}/reject"
        ]
        assert request_row(rid)["status"] == "pending"

    def test_b5_stale_session_user_cannot_act(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, 9999)  # no users row

        resp = accept(client, rid)

        assert resp.status_code == 404
        assert request_row(rid)["status"] == "pending"
        assert friendship_rows() == []


class TestStateMachine:
    """C1–C5: processed or nonexistent requests are not actionable."""

    def test_c1_double_accept_is_404_and_idempotent(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["alice"])

        assert accept(client, rid).status_code == 303
        assert accept(client, rid).status_code == 404

        assert request_row(rid)["status"] == "accepted"
        assert len(friendship_rows()) == 2  # no duplicates

    def test_c2_cannot_accept_rejected_request(self, client, users):
        rid = make_request(users["bob"], users["alice"], status="rejected")
        login(client, users["alice"])

        resp = accept(client, rid)

        assert resp.status_code == 404
        assert request_row(rid)["status"] == "rejected"
        assert friendship_rows() == []

    def test_c3_cannot_reject_accepted_request(self, client, users):
        rid = make_request(users["bob"], users["alice"], status="accepted")
        make_friendship(users["alice"], users["bob"])
        make_friendship(users["bob"], users["alice"])
        login(client, users["alice"])

        resp = reject(client, rid)

        assert resp.status_code == 404
        assert request_row(rid)["status"] == "accepted"
        assert len(friendship_rows()) == 2  # pair untouched

    @pytest.mark.parametrize("action", ["accept", "reject"])
    def test_c4_nonexistent_request_id(self, client, users, action):
        login(client, users["alice"])

        url = f"/friends/requests/4242/{action}"
        resp = client.get(url)

        assert resp.status_code == 404
        assert db.query_one("SELECT * FROM friend_requests") is None
        assert friendship_rows() == []

    @pytest.mark.parametrize("action", ["accept", "reject"])
    def test_c5_non_integer_request_id(self, client, users, action):
        login(client, users["alice"])

        resp = client.get(f"/friends/requests/abc/{action}")

        assert resp.status_code == 404


class TestIsolation:
    """D1–D4: only the addressed request and its pair change."""

    def test_d1_other_pending_requests_untouched(self, client, users):
        bob_rid = make_request(users["bob"], users["alice"], created_at=OLD_TS)
        carol_rid = make_request(
            users["carol"], users["alice"], created_at="2020-01-02T00:00:00.000Z"
        )
        login(client, users["alice"])

        assert accept(client, bob_rid).status_code == 303

        assert request_row(carol_rid)["status"] == "pending"
        assert [(r["user_id"], r["friend_id"]) for r in friendship_rows()] == [
            (users["alice"], users["bob"]),
            (users["bob"], users["alice"]),
        ]

    def test_d2_accept_with_preexisting_one_way_friendship_is_idempotent(
        self, client, users
    ):
        rid = make_request(users["bob"], users["alice"])
        make_friendship(users["alice"], users["bob"])  # anomaly: one direction only
        login(client, users["alice"])

        resp = accept(client, rid)

        assert resp.status_code == 303  # no IntegrityError/500
        assert [(r["user_id"], r["friend_id"]) for r in friendship_rows()] == [
            (users["alice"], users["bob"]),
            (users["bob"], users["alice"]),
        ]

    def test_d3_reject_leaves_unrelated_friendships_untouched(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        make_friendship(users["alice"], users["carol"])
        make_friendship(users["carol"], users["alice"])
        login(client, users["alice"])

        assert reject(client, rid).status_code == 303

        assert [(r["user_id"], r["friend_id"]) for r in friendship_rows()] == [
            (users["alice"], users["carol"]),
            (users["carol"], users["alice"]),
        ]

    def test_d4_accept_does_not_touch_other_requests_of_the_requester(
        self, client, users
    ):
        rid = make_request(users["bob"], users["alice"])
        other_rid = make_request(users["bob"], users["dave"])
        login(client, users["alice"])

        assert accept(client, rid).status_code == 303

        assert request_row(other_rid)["status"] == "pending"
        assert {(r["user_id"], r["friend_id"]) for r in friendship_rows()} == {
            (users["alice"], users["bob"]),
            (users["bob"], users["alice"]),
        }


class TestShell:
    """E1–E3: mounting contract of the self-built FP-002 shell."""

    def test_e1_url_map_contains_both_action_rules(self):
        url_map = create_app().url_map

        for action in ("accept", "reject"):
            rule = next(
                r for r in url_map.iter_rules() if r.rule.endswith(f"/{action}")
            )
            assert rule.rule == f"/friends/requests/<int:req_id>/{action}"
            assert {"GET", "POST"} <= rule.methods

    def test_e2_secret_key_follows_env(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_SECRET_KEY", "fp008-test-secret")
        assert create_app().secret_key == "fp008-test-secret"

    def test_e3_unallowed_method_is_405(self, client, users):
        rid = make_request(users["bob"], users["alice"])
        login(client, users["alice"])

        resp = client.put(f"/friends/requests/{rid}/accept")

        assert resp.status_code == 405
        assert request_row(rid)["status"] == "pending"
