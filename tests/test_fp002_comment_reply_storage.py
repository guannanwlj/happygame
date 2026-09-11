"""FP-002 tests: comment reply relation storage.

Scenarios documented in docs/test-cases/fp002-comment-reply-storage.md. Every
test gets a fresh temporary database file through the SOCIAL_DB environment
variable.
"""

import sqlite3

import pytest

from social_app import comments
from social_app import db

LEGACY_COMMENTS_DDL = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    NOT NULL UNIQUE,
  password_hash TEXT    NOT NULL,
  created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS posts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id  INTEGER NOT NULL REFERENCES users(id),
  content    TEXT    NOT NULL,
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS comments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id    INTEGER NOT NULL REFERENCES posts(id),
  author_id  INTEGER NOT NULL REFERENCES users(id),
  content    TEXT    NOT NULL,
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


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


def insert_post(author_id: int, content: str = "p1") -> int:
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (author_id, content),
    )
    return cur.lastrowid


def comment_columns() -> dict[str, sqlite3.Row]:
    rows = db.query_all("PRAGMA table_info(comments)")
    return {row["name"]: row for row in rows}


class TestTopLevelComment:
    """Acceptance 1: an omitted/None parent stores a top-level comment."""

    def test_top_level_comment_has_null_parent(self):
        user = insert_user("alice")
        post = insert_post(user)
        comment_id = comments.add_comment(post, user, "c1")
        row = db.query_one("SELECT parent_id FROM comments WHERE id = ?", (comment_id,))
        assert row["parent_id"] is None

    def test_add_comment_without_parent_still_returns_id(self):
        user = insert_user("alice")
        post = insert_post(user)
        comment_id = comments.add_comment(post, user, "c1")
        assert isinstance(comment_id, int)

    def test_explicit_none_parent_is_top_level(self):
        user = insert_user("alice")
        post = insert_post(user)
        comment_id = comments.add_comment(post, user, "c1", parent_id=None)
        assert db.query_one(
            "SELECT parent_id FROM comments WHERE id = ?", (comment_id,)
        )["parent_id"] is None


class TestReply:
    """Acceptance 2: a reply stores its top-level parent id."""

    def test_reply_points_to_parent(self):
        user = insert_user("alice")
        post = insert_post(user)
        parent = comments.add_comment(post, user, "c1")
        reply = comments.add_comment(post, user, "c2", parent_id=parent)
        row = db.query_one("SELECT parent_id FROM comments WHERE id = ?", (reply,))
        assert row["parent_id"] == parent

    def test_get_comment_returns_parent_id(self):
        user = insert_user("alice")
        post = insert_post(user)
        parent = comments.add_comment(post, user, "c1")
        reply = comments.add_comment(post, user, "c2", parent_id=parent)
        row = comments.get_comment(reply)
        assert row["parent_id"] == parent
        assert {"id", "post_id", "author_id", "content", "created_at", "parent_id"} <= set(
            row.keys()
        )

    def test_missing_parent_raises(self):
        user = insert_user("alice")
        post = insert_post(user)
        with pytest.raises(sqlite3.IntegrityError):
            comments.add_comment(post, user, "reply", parent_id=999)


class TestGetComment:
    """Contract for the new single-row reader."""

    def test_get_comment_top_level(self):
        user = insert_user("alice")
        post = insert_post(user)
        comment_id = comments.add_comment(post, user, "c1")
        row = comments.get_comment(comment_id)
        assert row["id"] == comment_id
        assert row["content"] == "c1"
        assert row["parent_id"] is None

    def test_get_comment_missing_returns_none(self):
        assert comments.get_comment(12345) is None


class TestListComments:
    """Acceptance 4: ascending order and the parent_id column are preserved."""

    def test_list_comments_includes_parent_id_and_ascending(self):
        user = insert_user("alice")
        post = insert_post(user)
        db.execute(
            "INSERT INTO comments (post_id, author_id, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (post, user, "c1", "2026-01-01T00:00:00Z"),
        )
        parent = db.query_one("SELECT id FROM comments WHERE content = 'c1'")["id"]
        for at, content, pid in [
            ("2026-01-01T00:00:02Z", "c3", None),
            ("2026-01-01T00:00:01Z", "c2", parent),
        ]:
            db.execute(
                "INSERT INTO comments (post_id, author_id, content, created_at, parent_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (post, user, content, at, pid),
            )
        rows = comments.list_comments(post)
        assert [r["content"] for r in rows] == ["c1", "c2", "c3"]
        assert [r["parent_id"] for r in rows] == [None, parent, None]
        assert "parent_id" in rows[0].keys()

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

    def test_list_comments_empty(self):
        user = insert_user("alice")
        post = insert_post(user)
        assert comments.list_comments(post) == []


class TestSchemaUpgrade:
    """Acceptance 3/5: legacy databases gain the column, idempotently."""

    def _build_legacy_db(self, path: str) -> None:
        with sqlite3.connect(path) as conn:
            conn.executescript(LEGACY_COMMENTS_DDL)
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES ('alice', 'h')"
            )
            conn.execute("INSERT INTO posts (author_id, content) VALUES (1, 'p1')")
            conn.execute(
                "INSERT INTO comments (post_id, author_id, content)"
                " VALUES (1, 1, 'legacy')"
            )

    def test_upgrade_adds_parent_id_to_legacy_db(self, temp_db_path):
        self._build_legacy_db(temp_db_path)
        db.init_db()
        assert "parent_id" in comment_columns()

    def test_legacy_comment_readable_and_null_parent(self, temp_db_path):
        self._build_legacy_db(temp_db_path)
        db.init_db()
        row = comments.get_comment(1)
        assert row["content"] == "legacy"
        assert row["parent_id"] is None

    def test_reply_works_after_upgrade(self, temp_db_path):
        self._build_legacy_db(temp_db_path)
        db.init_db()
        reply = comments.add_comment(1, 1, "reply", parent_id=1)
        assert comments.get_comment(reply)["parent_id"] == 1

    def test_init_db_idempotent(self, temp_db_path):
        db.init_db()
        db.init_db()
        db.init_db()
        user = insert_user("bob")
        post = insert_post(user)
        comments.add_comment(post, user, "still here")
        with db.get_connection() as conn:
            db.init_db(conn)
        assert [c["content"] for c in comments.list_comments(post)] == ["still here"]
        assert "parent_id" in comment_columns()

    def test_columns_after_upgrade(self, temp_db_path):
        db.init_db()
        columns = {row["name"] for row in db.query_all("PRAGMA table_info(comments)")}
        assert columns == {
            "id",
            "post_id",
            "author_id",
            "content",
            "created_at",
            "parent_id",
        }
        post_columns = {row["name"] for row in db.query_all("PRAGMA table_info(posts)")}
        assert post_columns == {"id", "author_id", "content", "created_at"}
