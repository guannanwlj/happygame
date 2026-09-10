"""FP-011 tests: follow rule validation and write (social_app.follow_service).

Scenarios documented in docs/test-cases/fp011-follow-logic.md. Every test gets
a fresh temporary database file through the SOCIAL_DB environment variable and
seeds users A (`alice`) and B (`bob`).
"""

import pytest

from social_app import db
from social_app import follow_service
from social_app.follow_service import FollowError, follow


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


@pytest.fixture
def users():
    """Seed alice/bob and return their ids."""
    alice = insert_user("alice")
    bob = insert_user("bob")
    return alice, bob


def insert_user(username: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, "hash"),
    )
    return cur.lastrowid


def follow_rows() -> list[tuple[int, int]]:
    return [
        (r["follower_id"], r["followee_id"])
        for r in db.query_all(
            "SELECT follower_id, followee_id FROM follows ORDER BY id"
        )
    ]


class TestHappyPath:
    """A1–A3: validated follow writes exactly one directed row."""

    def test_follow_creates_directed_row(self, users):
        alice, bob = users
        assert follow(alice, "bob") is None
        assert follow_rows() == [(alice, bob)]

    def test_follow_does_not_create_reverse(self, users):
        alice, bob = users
        follow(alice, "bob")
        assert (bob, alice) not in follow_rows()

    def test_follow_multiple_targets(self, users):
        alice, bob = users
        carol = insert_user("carol")
        follow(alice, "bob")
        follow(alice, "carol")
        assert follow_rows() == [(alice, bob), (alice, carol)]


class TestIdempotence:
    """B1–B2: repeating a follow is a silent no-op."""

    def test_repeat_follow_does_not_raise(self, users):
        alice, bob = users
        follow(alice, "bob")
        follow(alice, "bob")
        assert follow_rows() == [(alice, bob)]

    def test_repeat_follow_keeps_single_row(self, users):
        alice, bob = users
        for _ in range(3):
            follow(alice, "bob")
        assert follow_rows() == [(alice, bob)]


class TestRuleViolations:
    """C1–C4: login, target existence and self-follow messages."""

    def test_anonymous_raises(self):
        with pytest.raises(FollowError) as excinfo:
            follow(None, "bob")
        assert str(excinfo.value) == "未登录"

    def test_missing_target_raises(self, users):
        alice, _ = users
        with pytest.raises(FollowError) as excinfo:
            follow(alice, "nobody")
        assert str(excinfo.value) == "用户不存在"

    def test_self_follow_raises(self, users):
        alice, _ = users
        with pytest.raises(FollowError) as excinfo:
            follow(alice, "alice")
        assert str(excinfo.value) == "不能关注自己"

    def test_anonymous_wins_over_missing_target(self):
        with pytest.raises(FollowError) as excinfo:
            follow(None, "nobody")
        assert str(excinfo.value) == "未登录"


class TestNoSideEffectsOnRejection:
    """D1–D3: rejected requests never write to follows."""

    def test_self_follow_writes_nothing(self, users):
        alice, _ = users
        with pytest.raises(FollowError):
            follow(alice, "alice")
        assert follow_rows() == []

    def test_missing_target_writes_nothing(self, users):
        alice, _ = users
        with pytest.raises(FollowError):
            follow(alice, "nobody")
        assert follow_rows() == []

    def test_anonymous_writes_nothing(self):
        with pytest.raises(FollowError):
            follow(None, "bob")
        assert follow_rows() == []


class TestExceptionContract:
    """E1–E2: FollowError shape and edge usernames."""

    def test_follow_error_is_exception(self):
        assert issubclass(FollowError, Exception)

    @pytest.mark.parametrize("username", ["", "   ", "nobody"])
    def test_blank_or_unknown_target_raises_missing(self, users, username):
        alice, _ = users
        with pytest.raises(FollowError) as excinfo:
            follow(alice, username)
        assert str(excinfo.value) == "用户不存在"


class TestWriteDelegation:
    """F1–F2: validated requests delegate to FP-004's add_follow."""

    def test_calls_add_follow_with_resolved_id(self, users, monkeypatch):
        alice, bob = users
        calls = []
        monkeypatch.setattr(
            follow_service, "add_follow", lambda f, t: calls.append((f, t))
        )
        follow(alice, "bob")
        assert calls == [(alice, bob)]

    @pytest.mark.parametrize(
        ("actor", "target"),
        [(None, "bob"), ("alice", "nobody"), ("alice", "alice")],
    )
    def test_invalid_request_never_calls_add_follow(
        self, users, monkeypatch, actor, target
    ):
        alice, _ = users
        actor_id = alice if actor == "alice" else None
        calls = []
        monkeypatch.setattr(
            follow_service, "add_follow", lambda f, t: calls.append((f, t))
        )
        with pytest.raises(FollowError):
            follow(actor_id, target)
        assert calls == []
