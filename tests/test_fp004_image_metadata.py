"""FP-004 tests: post-image metadata persistence.

Scenarios documented in docs/test-cases/fp004-image-metadata.md. Every test
gets a fresh temporary database file through the SOCIAL_DB environment
variable.
"""

import sqlite3

import pytest

from social_app import db
from social_app import post_images


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


def seed_post(username: str = "alice", content: str = "hello") -> int:
    return insert_post(insert_user(username), content)


def stored_rows(post_id: int) -> list[sqlite3.Row]:
    return db.query_all(
        "SELECT post_id, storage_name, position FROM post_images"
        " WHERE post_id = ? ORDER BY position",
        (post_id,),
    )


class TestSchema:
    def test_init_db_creates_post_images_table_and_index(self):
        tables = {
            r["name"]
            for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        indexes = {
            r["name"]
            for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert "post_images" in tables
        assert "idx_post_images_post" in indexes

    def test_upgrade_old_database_without_post_images(self, temp_db_path):
        # Old DDL: only the pre-FP-004 tables, plus live post data.
        old_ddl = """
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
        """
        conn = sqlite3.connect(temp_db_path)
        conn.executescript(old_ddl)
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('old_user', 'hash')")
        conn.execute("INSERT INTO posts (author_id, content) VALUES (1, 'old post')")
        conn.commit()
        conn.close()

        db.init_db()  # upgrade

        tables = {
            r["name"]
            for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "post_images" in tables
        posts = db.query_all("SELECT id, content FROM posts")
        assert [(r["id"], r["content"]) for r in posts] == [(1, "old post")]

    def test_init_db_is_idempotent(self):
        pid = seed_post()
        post_images.save_post_images(pid, ["a.png"])
        db.init_db()  # repeat upgrade on an already-upgraded DB
        db.init_db()
        rows = stored_rows(pid)
        assert [(r["storage_name"], r["position"]) for r in rows] == [("a.png", 1)]


class TestSavePostImages:
    def test_saves_names_with_positions_in_submitted_order(self):
        pid = seed_post()
        post_images.save_post_images(pid, ["a.png", "b.png", "c.png"])
        rows = stored_rows(pid)
        assert len(rows) == 3
        assert [(r["storage_name"], r["position"]) for r in rows] == [
            ("a.png", 1),
            ("b.png", 2),
            ("c.png", 3),
        ]

    def test_empty_list_writes_no_rows(self):
        pid = seed_post()
        post_images.save_post_images(pid, [])
        assert stored_rows(pid) == []

    def test_duplicate_position_raises_integrity_error(self):
        pid = seed_post()
        post_images.save_post_images(pid, ["a.png"])
        with pytest.raises(sqlite3.IntegrityError):
            post_images.save_post_images(pid, ["again.png"])

    def test_passed_conn_does_not_commit_caller_controls_rollback(self):
        pid = seed_post()
        conn = db.get_connection()
        try:
            post_images.save_post_images(pid, ["x.png"], conn=conn)
            conn.rollback()  # whole-post rollback driven by the caller
        finally:
            conn.close()
        assert stored_rows(pid) == []


class TestListPostImages:
    def test_returns_rows_sorted_by_position_with_expected_keys(self):
        pid = seed_post()
        post_images.save_post_images(pid, ["c.png", "a.png", "b.png"])
        listed = post_images.list_post_images(pid)
        assert [(item["storage_name"], item["position"]) for item in listed] == [
            ("c.png", 1),
            ("a.png", 2),
            ("b.png", 3),
        ]
        for item in listed:
            assert set(item) == {"image_id", "post_id", "storage_name", "position"}
            assert item["post_id"] == pid
            assert isinstance(item["image_id"], int)

    def test_post_without_images_returns_empty_list(self):
        pid = seed_post()
        assert post_images.list_post_images(pid) == []

    def test_only_returns_images_of_the_requested_post(self):
        author = insert_user("alice")
        first = insert_post(author, "with images")
        second = insert_post(author, "text only")
        post_images.save_post_images(first, ["one.png", "two.png"])

        listed = post_images.list_post_images(second)
        assert listed == []

        listed_first = post_images.list_post_images(first)
        assert [item["storage_name"] for item in listed_first] == ["one.png", "two.png"]
