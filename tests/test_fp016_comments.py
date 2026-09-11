"""FP-016 tests: comment data and storage.

Scenarios documented in docs/test-cases/fp016-comments.md. Every test gets a
fresh temporary database file through the SOCIAL_DB environment variable.
"""

import sqlite3

import pytest

from social_app import comments
from social_app import db


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


def insert_post(author_id: int, content: str = "post") -> int:
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (author_id, content),
    )
    return cur.lastrowid


def comment_columns() -> dict[str, sqlite3.Row]:
    rows = db.query_all("PRAGMA table_info(comments)")
    return {row["name"]: row for row in rows}


class TestSchema:
    """Acceptance 1 + hygiene: comments table created with the right shape."""

    def test_init_db_creates_comments_with_fks(self):
        columns = comment_columns()
        assert {"id", "post_id", "author_id", "content", "created_at"} <= set(columns)

        post_fk = db.query_all("PRAGMA foreign_key_list(comments)")
        targets = {(row["from"], row["table"], row["to"]) for row in post_fk}
        assert ("post_id", "posts", "id") in targets
        assert ("author_id", "users", "id") in targets

        assert columns["post_id"]["notnull"] == 1
        assert columns["author_id"]["notnull"] == 1
        assert columns["content"]["notnull"] == 1
        assert columns["created_at"]["notnull"] == 1

    def test_comments_post_index_present(self):
        indexes = {
            row["name"]
            for row in db.query_all("PRAGMA index_list(comments)")
        }
        assert "idx_comments_post" in indexes

    def test_init_db_idempotent(self):
        user = insert_user("alice")
        post = insert_post(user)
        comments.add_comment(post, user, "hello")
        db.init_db()
        assert len(comments.list_comments(post)) == 1

    def test_legacy_tables_still_present(self):
        tables = {
            row["name"]
            for row in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {
            "users",
            "posts",
            "follows",
            "friend_requests",
            "friendships",
            "comments",
        } <= tables

    def test_legacy_posts_columns_unchanged(self):
        columns = {
            row["name"] for row in db.query_all("PRAGMA table_info(posts)")
        }
        assert columns == {"id", "author_id", "content", "created_at"}


class TestAddComment:
    """Acceptance 2: write a comment and return its id."""

    def test_add_comment_returns_id_and_row(self):
        user = insert_user("alice")
        post = insert_post(user)
        comment_id = comments.add_comment(post, user, "hello")

        assert isinstance(comment_id, int)
        row = db.query_one("SELECT * FROM comments WHERE id = ?", (comment_id,))
        assert row["post_id"] == post
        assert row["author_id"] == user
        assert row["content"] == "hello"
        assert row["created_at"]

    def test_add_comment_ids_increase(self):
        user = insert_user("alice")
        post = insert_post(user)
        first = comments.add_comment(post, user, "one")
        second = comments.add_comment(post, user, "two")
        assert second > first

    def test_missing_foreign_keys_raise(self):
        with pytest.raises(sqlite3.IntegrityError):
            comments.add_comment(999, 1000, "orphan")

    def test_blank_content_stored_verbatim(self):
        user = insert_user("alice")
        post = insert_post(user)
        comment_id = comments.add_comment(post, user, "   ")
        row = db.query_one("SELECT content FROM comments WHERE id = ?", (comment_id,))
        assert row["content"] == "   "


class TestListComments:
    """Acceptance 3/4: ascending order, tie-break by id, empty list."""

    def test_list_comments_ordered_ascending(self):
        user = insert_user("alice")
        post = insert_post(user)
        for at, content in [
            ("2026-01-01T00:00:02Z", "second"),
            ("2026-01-01T00:00:00Z", "first"),
            ("2026-01-01T00:00:01Z", "middle"),
        ]:
            db.execute(
                "INSERT INTO comments (post_id, author_id, content, created_at)"
                " VALUES (?, ?, ?, ?)",
                (post, user, content, at),
            )
        assert [r["content"] for r in comments.list_comments(post)] == [
            "first",
            "middle",
            "second",
        ]

    def test_list_comments_tie_break_by_id(self):
        user = insert_user("alice")
        post = insert_post(user)
        for content in ["a", "b", "c"]:
            db.execute(
                "INSERT INTO comments (post_id, author_id, content, created_at)"
                " VALUES (?, ?, ?, ?)",
                (post, user, content, "2026-01-01T00:00:00Z"),
            )
        assert [r["content"] for r in comments.list_comments(post)] == ["a", "b", "c"]

    def test_list_comments_scoped_to_post(self):
        user = insert_user("alice")
        post_p = insert_post(user, "P")
        post_q = insert_post(user, "Q")
        comments.add_comment(post_p, user, "for P")
        comments.add_comment(post_q, user, "for Q")
        contents = [r["content"] for r in comments.list_comments(post_p)]
        assert contents == ["for P"]

    def test_list_comments_returns_rows_with_contract_columns(self):
        user = insert_user("alice")
        post = insert_post(user)
        comments.add_comment(post, user, "hello")
        row = comments.list_comments(post)[0]
        assert isinstance(row, sqlite3.Row)
        assert {"id", "post_id", "author_id", "content", "created_at"} <= set(
            row.keys()
        )

    def test_list_comments_empty(self):
        user = insert_user("alice")
        post = insert_post(user)
        result = comments.list_comments(post)
        assert result == []
        assert isinstance(result, list)
