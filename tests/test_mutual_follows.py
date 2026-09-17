"""FP-001 tests: mutual-follow check primitive (social_app.mutual_follows).

Scenarios documented in docs/test-cases/fp001-mutual-follow-check.md. Every
test gets a fresh temporary database file through the SOCIAL_DB environment
variable and an initialized base schema. Users are seeded by direct inserts
(card §6); follows are seeded through the existing ``add_follow`` and
"unfollow" is simulated with a direct ``DELETE FROM follows`` (the repo has
no unfollow entry point yet).
"""

import pytest

from social_app import db
from social_app.follows import add_follow
from social_app.mutual_follows import is_mutual_follow


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so tests never touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    yield str(path)


@pytest.fixture(autouse=True)
def initialized_db(temp_db_path):
    """Start every test from an initialized base schema."""
    db.init_db()
    return temp_db_path


def insert_user(username: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, "hash"),
    )
    return cur.lastrowid


@pytest.fixture
def users(initialized_db):
    """Three unrelated users A, B, C with no follows between them."""
    return {"a": insert_user("alice"), "b": insert_user("bob"), "c": insert_user("carol")}


def follow_rows() -> set[tuple[int, int]]:
    rows = db.query_all("SELECT follower_id, followee_id FROM follows")
    return {(row["follower_id"], row["followee_id"]) for row in rows}


class TestMutualPair:
    """Acceptance 1: A→B and B→A both present."""

    def test_mutual_pair_returns_true(self, users):
        add_follow(users["a"], users["b"])
        add_follow(users["b"], users["a"])
        assert is_mutual_follow(users["a"], users["b"]) is True

    def test_mutual_pair_is_symmetric(self, users):
        add_follow(users["a"], users["b"])
        add_follow(users["b"], users["a"])
        assert is_mutual_follow(users["b"], users["a"]) is True


class TestOneWayPair:
    """Acceptance 2: only A→B present."""

    def test_one_way_returns_false(self, users):
        add_follow(users["a"], users["b"])
        assert is_mutual_follow(users["a"], users["b"]) is False

    def test_one_way_reversed_arguments_also_false(self, users):
        add_follow(users["a"], users["b"])
        assert is_mutual_follow(users["b"], users["a"]) is False


class TestNoRelationship:
    """Acceptance 3: no follows rows between the pair."""

    def test_no_rows_returns_false(self, users):
        assert is_mutual_follow(users["a"], users["b"]) is False

    def test_unrelated_third_user_returns_false(self, users):
        add_follow(users["a"], users["b"])
        assert is_mutual_follow(users["a"], users["c"]) is False


class TestRealTimeNoSnapshot:
    """Acceptance 4: deleting a follow flips the answer on the next call."""

    def test_delete_reverse_follow_flips_to_false(self, users):
        a, b = users["a"], users["b"]
        add_follow(a, b)
        add_follow(b, a)
        assert is_mutual_follow(a, b) is True
        db.execute("DELETE FROM follows WHERE follower_id = ? AND followee_id = ?", (b, a))
        assert is_mutual_follow(a, b) is False

    def test_re_follow_restores_true(self, users):
        a, b = users["a"], users["b"]
        add_follow(a, b)
        add_follow(b, a)
        db.execute("DELETE FROM follows WHERE follower_id = ? AND followee_id = ?", (b, a))
        add_follow(b, a)
        assert is_mutual_follow(a, b) is True


class TestEdgeCases:
    """Boundaries: legacy-table isolation, self-pair, purity."""

    def test_legacy_friendship_rows_do_not_count(self, users):
        """Decision must read follows only, never the friendships legacy table."""
        a, b = users["a"], users["b"]
        db.execute(
            "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?), (?, ?)",
            (a, b, b, a),
        )
        assert follow_rows() == set()
        assert is_mutual_follow(a, b) is False

    def test_self_pair_returns_false(self, users):
        """Boundary note (card §7): undefined upstream, no promise made."""
        assert is_mutual_follow(users["a"], users["a"]) is False

    def test_call_does_not_mutate_follows(self, users):
        a, b = users["a"], users["b"]
        add_follow(a, b)
        add_follow(b, a)
        before = follow_rows()
        is_mutual_follow(a, b)
        assert follow_rows() == before
