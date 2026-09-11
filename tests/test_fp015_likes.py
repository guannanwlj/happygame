"""FP-015 tests: like data & storage primitives.

Scenarios documented in docs/test-cases/fp015-likes.md. Every test gets a
fresh temporary database file through the SOCIAL_DB environment variable.
"""

import sqlite3

import pytest

from social_app import db
from social_app import likes


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


def insert_post(author_id: int, content: str = "hello") -> int:
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (author_id, content),
    )
    return cur.lastrowid


def like_rows() -> list[tuple[int, int]]:
    return [
        (r["user_id"], r["post_id"])
        for r in db.query_all("SELECT user_id, post_id FROM likes ORDER BY id")
    ]


def tables() -> set[str]:
    return {
        r["name"]
        for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


class TestSchema:
    """Acceptance 1: likes table created with UNIQUE(user_id, post_id)."""

    def test_init_db_creates_likes_with_unique(self):
        assert "likes" in tables()
        ddl = db.query_one(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'likes'"
        )["sql"]
        assert "UNIQUE" in ddl.upper()

    def test_raw_duplicate_insert_violates_unique(self):
        a = insert_user("alice")
        p = insert_post(a)
        db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (a, p))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (a, p))

    def test_legacy_tables_still_present(self):
        assert {
            "users",
            "posts",
            "follows",
            "friend_requests",
            "friendships",
        } <= tables()


class TestAddLike:
    """Acceptance 2: insert once, idempotent on repeat."""

    def test_add_like_inserts_and_is_idempotent(self):
        a = insert_user("alice")
        p = insert_post(a)
        assert likes.add_like(a, p) is True
        assert like_rows() == [(a, p)]
        assert likes.add_like(a, p) is False
        assert like_rows() == [(a, p)]

    def test_different_users_like_same_post(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        assert likes.add_like(a, p) is True
        assert likes.add_like(b, p) is True
        assert like_rows() == [(a, p), (b, p)]


class TestRemoveLike:
    """Acceptance 3: delete once, idempotent on repeat."""

    def test_remove_like_deletes_and_is_idempotent(self):
        a = insert_user("alice")
        p = insert_post(a)
        likes.add_like(a, p)
        assert likes.remove_like(a, p) is True
        assert like_rows() == []
        assert likes.remove_like(a, p) is False
        assert like_rows() == []

    def test_remove_leaves_other_users_like(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        likes.add_like(a, p)
        likes.add_like(b, p)
        likes.remove_like(a, p)
        assert like_rows() == [(b, p)]


class TestIsLiked:
    """Acceptance 4: existence lookup."""

    def test_is_liked_true_false(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        assert likes.is_liked(a, p) is False
        likes.add_like(a, p)
        assert likes.is_liked(a, p) is True
        assert likes.is_liked(b, p) is False
        likes.remove_like(a, p)
        assert likes.is_liked(a, p) is False


class TestPersistenceAndIntegrity:
    """Edge cases: reopen idempotence and foreign-key enforcement."""

    def test_like_survives_reopen(self):
        a = insert_user("alice")
        p = insert_post(a)
        likes.add_like(a, p)
        db.init_db()
        assert likes.is_liked(a, p) is True
        assert like_rows() == [(a, p)]

    def test_missing_user_or_post_raises_integrity_error(self):
        a = insert_user("alice")
        p = insert_post(a)
        with pytest.raises(sqlite3.IntegrityError):
            likes.add_like(999, p)
        with pytest.raises(sqlite3.IntegrityError):
            likes.add_like(a, 999)
