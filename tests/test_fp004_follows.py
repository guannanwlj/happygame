"""FP-004 tests: one-directional follow relationship storage.

Scenarios documented in docs/test-cases/fp004-follows.md. Every test gets a
fresh temporary database file through the SOCIAL_DB environment variable.
"""

import sqlite3

import pytest

from social_app import db
from social_app import follows


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


class TestAddFollow:
    """Acceptances 1-2: one-directional insert, idempotent on repeat."""

    def test_add_follow_creates_directed_row(self):
        a, b = insert_user("alice"), insert_user("bob")
        assert follows.add_follow(a, b) is True
        assert follow_rows() == [(a, b)]

    def test_add_follow_does_not_create_reverse(self):
        a, b = insert_user("alice"), insert_user("bob")
        follows.add_follow(a, b)
        assert (b, a) not in follow_rows()

    def test_add_follow_idempotent(self):
        a, b = insert_user("alice"), insert_user("bob")
        assert follows.add_follow(a, b) is True
        assert follows.add_follow(a, b) is False
        assert follow_rows() == [(a, b)]


class TestIsFollowing:
    """Acceptance 3: directional lookup."""

    def test_is_following_true_for_followed(self):
        a, b = insert_user("alice"), insert_user("bob")
        follows.add_follow(a, b)
        assert follows.is_following(a, b) is True

    def test_is_following_false_for_reverse(self):
        a, b = insert_user("alice"), insert_user("bob")
        follows.add_follow(a, b)
        assert follows.is_following(b, a) is False


class TestListFollowees:
    """Acceptance 4: list followee ids."""

    def test_lists_followees_in_order(self):
        a, b, c = insert_user("alice"), insert_user("bob"), insert_user("carol")
        follows.add_follow(a, b)
        follows.add_follow(a, c)
        assert follows.list_followees(a) == [b, c]

    def test_lists_empty_when_nothing_followed(self):
        d = insert_user("dave")
        assert follows.list_followees(d) == []

    def test_returns_plain_ints(self):
        a, b = insert_user("alice"), insert_user("bob")
        follows.add_follow(a, b)
        result = follows.list_followees(a)
        assert result and all(type(x) is int for x in result)


class TestPersistence:
    """Acceptance 5: record survives closing and reopening the file."""

    def test_follow_survives_reopen(self):
        a, b = insert_user("alice"), insert_user("bob")
        follows.add_follow(a, b)

        db.init_db()  # reopen/re-init same file
        assert follows.is_following(a, b) is True
        assert follow_rows() == [(a, b)]


class TestConstraints:
    """Acceptance 6 + schema integrity."""

    def test_missing_users_raise_integrity_error(self):
        with pytest.raises(sqlite3.IntegrityError):
            follows.add_follow(999, 1000)

    def test_init_db_idempotent_keeps_follows(self):
        db.init_db()
        tables = {
            r["name"]
            for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "follows" in tables

    def test_legacy_friend_tables_still_present(self):
        tables = {
            r["name"]
            for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"friend_requests", "friendships"} <= tables
