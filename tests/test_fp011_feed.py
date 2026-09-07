"""FP-011 tests: friends-feed timeline (social_app/feed.py, GET /feed).

Scenarios documented in docs/test-cases/fp011-friends-feed.md. Per task card
§6 the unmerged dependencies are mocked: login state is injected straight
into the Flask session (FP-003), friendships and posts are seeded directly
into the tables (FP-008/FP-010).
"""

import pytest

from social_app import db
from social_app.app import create_app
from social_app.auth import USER_ID_SESSION_KEY
from social_app.feed import FEED_SQL

EMPTY_STATE_TEXT = "暂无好友动态"
PAGE_TITLE = "好友动态"


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so tests never touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    yield str(path)


@pytest.fixture(autouse=True)
def initialized_db(temp_db_path):
    """Start every test from an initialized schema."""
    db.init_db()
    return temp_db_path


@pytest.fixture()
def client(temp_db_path):
    """Test client for the minimal app shell (schema init inside create_app)."""
    app = create_app()
    with app.test_client() as test_client:
        yield test_client


def insert_user(username: str, password_hash: str = "h1") -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    return cur.lastrowid


def insert_friendship_pair(user_id: int, friend_id: int) -> None:
    """Bidirectional two rows, what FP-008's accept flow will produce."""
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (user_id, friend_id),
        )
        conn.execute(
            "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (friend_id, user_id),
        )


def insert_post(author_id: int, content: str, created_at: str) -> None:
    db.execute(
        "INSERT INTO posts (author_id, content, created_at) VALUES (?, ?, ?)",
        (author_id, content, created_at),
    )


@pytest.fixture()
def seed():
    """Card §6 seed: users, alice's friendships, posts with staggered times."""
    ids = {
        "alice": insert_user("alice", "ha"),
        "bob": insert_user("bob", "hb"),
        "carol": insert_user("carol", "hc"),
        "dave": insert_user("dave", "hd"),
    }
    insert_friendship_pair(ids["alice"], ids["bob"])
    insert_friendship_pair(ids["alice"], ids["carol"])

    posts = {
        "bob_old": ("bob-old", "2026-09-01T10:00:00.000Z"),
        "carol_mid": ("carol-mid", "2026-09-02T12:00:00.000Z"),
        "bob_new": ("bob-new", "2026-09-03T09:00:00.000Z"),
    }
    insert_post(ids["bob"], *posts["bob_old"])
    insert_post(ids["carol"], *posts["carol_mid"])
    insert_post(ids["bob"], *posts["bob_new"])
    insert_post(ids["dave"], "dave-solo", "2026-09-04T08:00:00.000Z")
    insert_post(ids["alice"], "alice-own", "2026-09-05T07:00:00.000Z")
    return ids


def login(client, user_id: int) -> None:
    """FP-003 mock: inject login state via the session (card §6)."""
    with client.session_transaction() as session:
        session[USER_ID_SESSION_KEY] = user_id


def rendered_entries(data: bytes) -> list[bytes]:
    """Split the HTML on the per-post marker, dropping the part before it."""
    return data.split(b'class="post"')[1:]


class TestFriendsFeedTimeline:
    """A1/A2: visibility and ordering for a logged-in user with friends."""

    def test_all_friend_posts_visible_newest_first(self, client, seed):
        login(client, seed["alice"])
        response = client.get("/feed")

        assert response.status_code == 200
        entries = rendered_entries(response.data)
        assert len(entries) == 3

        expected = [
            ("bob", "bob-new", "2026-09-03T09:00:00.000Z"),
            ("carol", "carol-mid", "2026-09-02T12:00:00.000Z"),
            ("bob", "bob-old", "2026-09-01T10:00:00.000Z"),
        ]
        for entry, (username, content, created_at) in zip(entries, expected):
            assert username.encode() in entry  # author per entry
            assert created_at.encode() in entry  # publish time per entry
            assert content.encode() in entry  # content per entry

    def test_non_friend_and_own_posts_excluded(self, client, seed):
        login(client, seed["alice"])
        response = client.get("/feed")

        assert response.status_code == 200
        assert b"dave-solo" not in response.data
        assert b"alice-own" not in response.data
        assert len(rendered_entries(response.data)) == 3


class TestEmptyState:
    """A3: nothing visible → empty state, still 200."""

    def test_no_friends_at_all(self, client, seed):
        login(client, seed["dave"])
        response = client.get("/feed")

        assert response.status_code == 200
        assert EMPTY_STATE_TEXT.encode() in response.data
        assert b"bob-old" not in response.data

    def test_friends_without_posts(self, client, seed):
        erin = insert_user("erin", "he")
        frank = insert_user("frank", "hf")
        insert_friendship_pair(erin, frank)

        login(client, erin)
        response = client.get("/feed")

        assert response.status_code == 200
        assert EMPTY_STATE_TEXT.encode() in response.data
        assert len(rendered_entries(response.data)) == 0


class TestAuthenticationGate:
    """A4: anonymous access is bounced to the login page."""

    def test_anonymous_redirected_to_login(self, client, seed):
        response = client.get("/feed")

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"


class TestContractAndShell:
    """E1/E2: the §3.1 query contract and the base.html inheritance."""

    def test_contract_query_isolation_and_order(self, seed):
        rows = db.query_all(FEED_SQL, {"current_user_id": seed["alice"]})

        assert [(r["username"], r["content"]) for r in rows] == [
            ("bob", "bob-new"),
            ("carol", "carol-mid"),
            ("bob", "bob-old"),
        ]
        assert [r["created_at"] for r in rows] == sorted(
            (r["created_at"] for r in rows), reverse=True
        )

    def test_feed_template_extends_base_and_overrides_title(self, client, seed):
        login(client, seed["alice"])
        response = client.get("/feed")

        assert f"<title>{PAGE_TITLE}</title>".encode() in response.data
