"""FP-001 tests: comment like data & storage primitives.

Scenarios documented in docs/test-cases/fp001-comment-likes.md. Every test gets
a fresh temporary database file through the SOCIAL_DB environment variable.
"""

import sqlite3

import pytest

from social_app import comment_likes, db


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so tests never touch the repo."""
    path = tmp_path / "social_platform.db"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    yield str(path)


@pytest.fixture(autouse=True)
def initialized_db(temp_db_path):
    """Start every test from an initialized schema plus the card's seed data."""
    db.init_db()
    return temp_db_path


def insert_user(username: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, "hash"),
    )
    return cur.lastrowid


def insert_comment(author_id: int, content: str = "hello", post_id: int | None = None) -> int:
    if post_id is None:
        cur = db.execute(
            "INSERT INTO posts (author_id, content) VALUES (?, ?)",
            (author_id, "seed post"),
        )
        post_id = cur.lastrowid
    cur = db.execute(
        "INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
        (post_id, author_id, content),
    )
    return cur.lastrowid


def seed() -> tuple[int, int, int]:
    """Alice, Bob and a comment authored by Alice (card §6 seed)."""
    alice = insert_user("alice")
    bob = insert_user("bob")
    comment = insert_comment(alice)
    return alice, bob, comment


def like_rows() -> list[tuple[int, int]]:
    return [
        (r["user_id"], r["comment_id"])
        for r in db.query_all(
            "SELECT user_id, comment_id FROM comment_likes ORDER BY id"
        )
    ]


def post_of(comment_id: int) -> int:
    return db.query_one("SELECT post_id FROM comments WHERE id = ?", (comment_id,))[
        "post_id"
    ]


def tables() -> set[str]:
    return {
        r["name"]
        for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


class TestSchema:
    """Acceptance 1: comment_likes table created with UNIQUE(user_id, comment_id)."""

    def test_init_db_creates_comment_likes_with_unique(self):
        assert "comment_likes" in tables()
        ddl = db.query_one(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'comment_likes'"
        )["sql"]
        assert "UNIQUE" in ddl.upper()

    def test_raw_duplicate_insert_violates_unique(self):
        a, _, c = seed()
        db.execute(
            "INSERT INTO comment_likes (user_id, comment_id) VALUES (?, ?)", (a, c)
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO comment_likes (user_id, comment_id) VALUES (?, ?)", (a, c)
            )

    def test_legacy_tables_still_present(self):
        assert {"users", "posts", "comments", "likes"} <= tables()


class TestAddCommentLike:
    """Acceptance 1: insert once, idempotent on repeat."""

    def test_add_like_inserts_and_is_idempotent(self):
        _, b, c = seed()
        assert comment_likes.add_comment_like(b, c) is True
        assert like_rows() == [(b, c)]
        assert comment_likes.add_comment_like(b, c) is False
        assert like_rows() == [(b, c)]

    def test_different_users_like_same_comment(self):
        a, b, c = seed()
        assert comment_likes.add_comment_like(a, c) is True
        assert comment_likes.add_comment_like(b, c) is True
        assert like_rows() == [(a, c), (b, c)]


class TestRemoveCommentLike:
    """Acceptance 4: delete once, idempotent on repeat."""

    def test_remove_like_deletes_and_is_idempotent(self):
        _, b, c = seed()
        comment_likes.add_comment_like(b, c)
        assert comment_likes.remove_comment_like(b, c) is True
        assert comment_likes.count_comment_likes(c) == 0
        assert like_rows() == []
        assert comment_likes.remove_comment_like(b, c) is False
        assert like_rows() == []

    def test_remove_leaves_other_users_like(self):
        a, b, c = seed()
        comment_likes.add_comment_like(a, c)
        comment_likes.add_comment_like(b, c)
        comment_likes.remove_comment_like(a, c)
        assert like_rows() == [(b, c)]


class TestCountCommentLikes:
    """Acceptance 5: count starts at zero and increments independently."""

    def test_count_starts_at_zero_and_increments(self):
        a, b, c = seed()
        assert comment_likes.count_comment_likes(c) == 0
        comment_likes.add_comment_like(a, c)
        assert comment_likes.count_comment_likes(c) == 1
        comment_likes.add_comment_like(b, c)
        assert comment_likes.count_comment_likes(c) == 2
        comment_likes.remove_comment_like(a, c)
        assert comment_likes.count_comment_likes(c) == 1

    def test_count_is_per_comment(self):
        a, _, c1 = seed()
        other = insert_comment(a, "other")
        comment_likes.add_comment_like(a, other)
        assert comment_likes.count_comment_likes(c1) == 0
        assert comment_likes.count_comment_likes(other) == 1


class TestIsCommentLiked:
    """Acceptance: existence lookup."""

    def test_is_liked_true_false(self):
        a, b, c = seed()
        assert comment_likes.is_comment_liked(a, c) is False
        comment_likes.add_comment_like(a, c)
        assert comment_likes.is_comment_liked(a, c) is True
        assert comment_likes.is_comment_liked(b, c) is False
        comment_likes.remove_comment_like(a, c)
        assert comment_likes.is_comment_liked(a, c) is False


class TestPersistenceAndIntegrity:
    """Edge cases: reopen idempotence and foreign-key enforcement."""

    def test_like_survives_reopen(self):
        _, b, c = seed()
        comment_likes.add_comment_like(b, c)
        db.init_db()
        assert comment_likes.is_comment_liked(b, c) is True
        assert like_rows() == [(b, c)]

    def test_missing_user_or_comment_raises_integrity_error(self):
        _, b, c = seed()
        with pytest.raises(sqlite3.IntegrityError):
            comment_likes.add_comment_like(999, c)
        with pytest.raises(sqlite3.IntegrityError):
            comment_likes.add_comment_like(b, 999)


class TestExistingLikesUntouched:
    """Acceptance 2: post likes table structure and data are unchanged."""

    def test_likes_table_untouched(self):
        a, b, c = seed()
        post = post_of(c)
        db.execute(
            "INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (b, post)
        )
        before_ddl = db.query_one(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'likes'"
        )["sql"]
        before_count = db.query_one("SELECT COUNT(*) AS n FROM likes")["n"]

        db.init_db()
        comment_likes.add_comment_like(a, c)

        after_ddl = db.query_one(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'likes'"
        )["sql"]
        after_count = db.query_one("SELECT COUNT(*) AS n FROM likes")["n"]
        assert after_ddl == before_ddl
        assert after_count == before_count


class TestIndependenceFromPostLikes:
    """Comment likes have their own counter, separate from post likes."""

    def test_post_like_does_not_affect_comment_count(self):
        a, b, c = seed()
        post = post_of(c)
        db.execute(
            "INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (b, post)
        )
        assert comment_likes.count_comment_likes(c) == 0
        comment_likes.add_comment_like(a, c)
        assert comment_likes.count_comment_likes(c) == 1
