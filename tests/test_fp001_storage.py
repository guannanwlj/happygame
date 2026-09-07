"""FP-001 tests: core data model & persistent storage (social_app/db.py).

Scenarios documented in docs/test-cases/fp001-storage.md. Every test gets a
fresh temporary database file through the SOCIAL_DB environment variable.
"""

import sqlite3
from contextlib import closing

import pytest

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


def insert_user(username: str, password_hash: str = "h1") -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    return cur.lastrowid


def insert_friend_request(requester_id: int, addressee_id: int) -> int:
    cur = db.execute(
        "INSERT INTO friend_requests (requester_id, addressee_id) VALUES (?, ?)",
        (requester_id, addressee_id),
    )
    return cur.lastrowid


def insert_friendship(user_id: int, friend_id: int) -> int:
    cur = db.execute(
        "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)",
        (user_id, friend_id),
    )
    return cur.lastrowid


def insert_post(author_id: int, content: str) -> int:
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (author_id, content),
    )
    return cur.lastrowid


class TestPersistenceAcrossReopen:
    """Acceptance 1: data survives closing and reopening the same file."""

    def test_user_survives_reopen(self):
        uid = insert_user("alice", "hash-alice")
        snapshot = tuple(db.query_one("SELECT * FROM users WHERE id = ?", (uid,)))

        after = db.query_one("SELECT * FROM users WHERE id = ?", (uid,))
        assert after is not None
        assert tuple(after) == snapshot
        assert after["created_at"]  # default timestamp populated

    def test_friend_request_survives_reopen(self):
        a = insert_user("alice")
        b = insert_user("bob")
        rid = insert_friend_request(a, b)
        before = db.query_one("SELECT * FROM friend_requests WHERE id = ?", (rid,))
        snapshot = tuple(before)

        after = db.query_one("SELECT * FROM friend_requests WHERE id = ?", (rid,))
        assert after is not None
        assert tuple(after) == snapshot
        assert after["status"] == "pending"
        assert after["created_at"] and after["updated_at"]

    def test_friendships_survive_reopen(self):
        a = insert_user("alice")
        b = insert_user("bob")
        with db.transaction() as conn:
            conn.execute("INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (a, b))
            conn.execute("INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (b, a))

        rows = db.query_all(
            "SELECT * FROM friendships WHERE (user_id = ? AND friend_id = ?)"
            " OR (user_id = ? AND friend_id = ?)",
            (a, b, b, a),
        )
        assert len(rows) == 2
        snapshot = {tuple(r) for r in rows}

        reopened = db.query_all("SELECT * FROM friendships")
        assert {tuple(r) for r in reopened} == snapshot

    def test_post_survives_reopen(self):
        uid = insert_user("alice")
        pid = insert_post(uid, "hello world")
        before = db.query_one("SELECT * FROM posts WHERE id = ?", (pid,))

        after = db.query_one("SELECT * FROM posts WHERE id = ?", (pid,))
        assert after is not None
        assert tuple(after) == tuple(before)
        assert after["content"] == "hello world"
        assert after["created_at"]

    def test_seed_scenario_reopen(self, temp_db_path):
        """Card §6 seed: user, pending request, bidirectional friendship, post."""
        a = insert_user("alice", "ha")
        b = insert_user("bob", "hb")
        insert_friend_request(a, b)
        insert_friendship(a, b)
        insert_friendship(b, a)
        insert_post(b, "first post")

        # Simulate a service restart: fully new connection to the same file.
        with closing(db.get_connection()) as conn:
            users = conn.execute("SELECT username FROM users ORDER BY id").fetchall()
            requests = conn.execute("SELECT requester_id, addressee_id, status FROM friend_requests").fetchall()
            friends = conn.execute("SELECT user_id, friend_id FROM friendships ORDER BY user_id").fetchall()
            posts = conn.execute("SELECT author_id, content FROM posts").fetchall()

        assert [u["username"] for u in users] == ["alice", "bob"]
        assert [(r["requester_id"], r["addressee_id"], r["status"]) for r in requests] == [(a, b, "pending")]
        assert [(f["user_id"], f["friend_id"]) for f in friends] == [(a, b), (b, a)]
        assert [(p["author_id"], p["content"]) for p in posts] == [(b, "first post")]


class TestApiContract:
    """Acceptance 2: init/query/execute work and init_db is idempotent."""

    def test_db_path_env_variable(self, temp_db_path):
        assert db.db_path() == temp_db_path

    def test_db_path_default(self, monkeypatch):
        monkeypatch.delenv(db.DB_PATH_ENV, raising=False)
        assert db.db_path() == "social_platform.db"

    def test_init_db_creates_all_tables(self):
        tables = {
            r["name"]
            for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"users", "friend_requests", "friendships", "posts"} <= tables

    def test_init_db_idempotent(self):
        db.init_db()  # second run on same file
        with closing(db.get_connection()) as conn:  # third run, explicit conn
            db.init_db(conn)
        tables = {
            r["name"]
            for r in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"users", "friend_requests", "friendships", "posts"} <= tables

    def test_get_connection_row_factory(self):
        with closing(db.get_connection()) as conn:
            assert conn.row_factory is sqlite3.Row

    def test_get_connection_foreign_keys_on(self):
        with closing(db.get_connection()) as conn:
            pragma = conn.execute("PRAGMA foreign_keys").fetchone()
        assert pragma[0] == 1

    def test_foreign_keys_enforced(self):
        with pytest.raises(sqlite3.IntegrityError):
            insert_friend_request(999, 1000)
        with pytest.raises(sqlite3.IntegrityError):
            insert_friendship(999, 1000)
        with pytest.raises(sqlite3.IntegrityError):
            insert_post(999, "orphan")

    def test_execute_returns_usable_cursor(self):
        cur = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("alice", "h"),
        )
        assert cur.lastrowid == 1
        cur = db.execute("UPDATE users SET password_hash = ? WHERE id = ?", ("h2", 1))
        assert cur.rowcount == 1
        cur = db.execute("DELETE FROM users WHERE id = ?", (1,))
        assert cur.rowcount == 1
        assert db.query_one("SELECT * FROM users") is None

    def test_query_all_and_query_one(self):
        insert_user("alice")
        insert_user("bob")
        all_rows = db.query_all("SELECT * FROM users ORDER BY id")
        assert [r["username"] for r in all_rows] == ["alice", "bob"]
        assert isinstance(all_rows[0], sqlite3.Row)

        one = db.query_one("SELECT * FROM users WHERE username = ?", ("bob",))
        assert one["username"] == "bob"
        assert db.query_one("SELECT * FROM users WHERE username = ?", ("carol",)) is None

    def test_duplicate_username_rejected(self):
        insert_user("alice")
        with pytest.raises(sqlite3.IntegrityError):
            insert_user("alice")

    def test_duplicate_pending_request_rejected(self):
        a = insert_user("alice")
        b = insert_user("bob")
        insert_friend_request(a, b)
        with pytest.raises(sqlite3.IntegrityError):
            insert_friend_request(a, b)

    def test_duplicate_friendship_rejected(self):
        a = insert_user("alice")
        b = insert_user("bob")
        insert_friendship(a, b)
        with pytest.raises(sqlite3.IntegrityError):
            insert_friendship(a, b)

    def test_status_check_constraint(self):
        a = insert_user("alice")
        b = insert_user("bob")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO friend_requests (requester_id, addressee_id, status)"
                " VALUES (?, ?, ?)",
                (a, b, "bogus"),
            )


class TestTransaction:
    """Acceptance 3: transaction() atomicity."""

    def test_rollback_on_error(self):
        a = insert_user("alice")
        b = insert_user("bob")

        class Boom(RuntimeError):
            pass

        with pytest.raises(Boom):
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO friend_requests (requester_id, addressee_id) VALUES (?, ?)",
                    (a, b),
                )
                conn.execute(
                    "INSERT INTO posts (author_id, content) VALUES (?, ?)",
                    (a, "should not persist"),
                )
                raise Boom("second statement failed")

        assert db.query_one("SELECT * FROM friend_requests") is None
        assert db.query_one("SELECT * FROM posts") is None

    def test_commit_on_success(self):
        a = insert_user("alice")
        b = insert_user("bob")
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (a, b)
            )
            conn.execute(
                "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)", (b, a)
            )

        rows = db.query_all("SELECT user_id, friend_id FROM friendships ORDER BY user_id")
        assert [(r["user_id"], r["friend_id"]) for r in rows] == [(a, b), (b, a)]

    def test_connection_usable_inside_block(self):
        a = insert_user("alice")
        with db.transaction() as conn:
            conn.execute("INSERT INTO posts (author_id, content) VALUES (?, ?)", (a, "in txn"))
            row = conn.execute("SELECT content FROM posts").fetchone()
            assert row["content"] == "in txn"


class TestEnvSwitch:
    """D1: switching SOCIAL_DB switches the database file."""

    def test_env_switch_creates_independent_db(self, temp_db_path, monkeypatch):
        insert_user("alice")
        other = temp_db_path.replace(".db", "-other.db")
        monkeypatch.setenv(db.DB_PATH_ENV, other)

        db.init_db()
        assert db.query_one("SELECT * FROM users") is None  # fresh, independent
        insert_user("bob")
        assert len(list(db.query_all("SELECT * FROM users"))) == 1

        monkeypatch.setenv(db.DB_PATH_ENV, temp_db_path)  # original untouched
        assert [r["username"] for r in db.query_all("SELECT username FROM users")] == ["alice"]
