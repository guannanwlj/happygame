"""FP-023 tests: feed query module (social_app.feed).

Scenarios documented in docs/test-cases/fp023-feed-query.md. Every test gets a
fresh temporary database file through the SOCIAL_DB environment variable and an
initialized base schema. FP-016 has not landed yet, so the card §3.1 ``likes`` /
``comments`` DDL is applied in the temp DB before seeding interaction data
(card §6 mock strategy) — this keeps the module independently verifiable.
"""

import contextlib

import pytest

from social_app import db
from social_app import feed
from social_app.follows import add_follow

INTERACTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS likes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  post_id    INTEGER NOT NULL REFERENCES posts(id),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (user_id, post_id)
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
    """Start every test from an initialized base schema."""
    db.init_db()
    return temp_db_path


@pytest.fixture
def interaction_tables(initialized_db):
    """Create the FP-015/FP-016 tables from the card §3.1 DDL (card §6)."""
    with contextlib.closing(db.get_connection()) as conn:
        conn.executescript(INTERACTION_SCHEMA)
    return initialized_db


def table_names() -> set[str]:
    return {
        row["name"]
        for row in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def insert_user(username: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, "hash"),
    )
    return cur.lastrowid


def insert_post(author_id: int, content: str, created_at: str) -> int:
    cur = db.execute(
        "INSERT INTO posts (author_id, content, created_at) VALUES (?, ?, ?)",
        (author_id, content, created_at),
    )
    return cur.lastrowid


def insert_like(user_id: int, post_id: int, created_at: str = "2026-01-01T00:00:00Z") -> int:
    cur = db.execute(
        "INSERT INTO likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
        (user_id, post_id, created_at),
    )
    return cur.lastrowid


def insert_comment(post_id: int, author_id: int, content: str, created_at: str) -> int:
    cur = db.execute(
        "INSERT INTO comments (post_id, author_id, content, created_at) "
        "VALUES (?, ?, ?, ?)",
        (post_id, author_id, content, created_at),
    )
    return cur.lastrowid


@pytest.fixture
def seeded(interaction_tables):
    """Users A/B/C, A follows B, three posts, C unfollowed."""
    a = insert_user("alice")
    b = insert_user("bob")
    c = insert_user("carol")
    add_follow(a, b)
    post_b = insert_post(b, "bob old", "2026-01-01T00:00:00Z")
    post_a = insert_post(a, "alice new", "2026-01-02T00:00:00Z")
    post_c = insert_post(c, "carol hidden", "2026-01-03T00:00:00Z")
    return {
        "a": a,
        "b": b,
        "c": c,
        "post_a": post_a,
        "post_b": post_b,
        "post_c": post_c,
    }


class TestFeedOrdering:
    """Acceptances 1 and 4: self + followees, newest first, stable ties."""

    def test_feed_includes_self_and_followees_newest_first(self, seeded):
        rows = feed.get_feed(seeded["a"])
        assert [row["post_id"] for row in rows] == [seeded["post_a"], seeded["post_b"]]
        assert [row["username"] for row in rows] == ["alice", "bob"]

    def test_feed_excludes_unfollowed(self, seeded):
        rows = feed.get_feed(seeded["a"])
        assert seeded["post_c"] not in [row["post_id"] for row in rows]
        assert "carol hidden" not in [row["content"] for row in rows]

    def test_feed_for_followee_uses_their_own_followees(self, seeded):
        rows = feed.get_feed(seeded["b"])
        assert [row["post_id"] for row in rows] == [seeded["post_b"]]

    def test_feed_same_timestamp_orders_by_id_desc(self, interaction_tables):
        a = insert_user("alice")
        shared = "2026-01-01T00:00:00Z"
        first = insert_post(a, "first", shared)
        second = insert_post(a, "second", shared)
        rows = feed.get_feed(a)
        assert [row["post_id"] for row in rows] == [second, first]


class TestLikeAggregation:
    """Acceptance 2: like_count and liked_by_me per viewer."""

    def test_feed_aggregates_like_count_and_liked_by_me(self, seeded):
        insert_like(seeded["a"], seeded["post_b"])
        insert_like(seeded["c"], seeded["post_b"])
        row = {r["post_id"]: r for r in feed.get_feed(seeded["a"])}[seeded["post_b"]]
        assert row["like_count"] == 2
        assert row["liked_by_me"] is True

    def test_liked_by_me_is_viewer_specific(self, seeded):
        insert_like(seeded["a"], seeded["post_b"])
        viewed_as_a = {r["post_id"]: r for r in feed.get_feed(seeded["a"])}
        viewed_as_b = {r["post_id"]: r for r in feed.get_feed(seeded["b"])}
        assert viewed_as_a[seeded["post_b"]]["liked_by_me"] is True
        assert viewed_as_b[seeded["post_b"]]["liked_by_me"] is False
        assert viewed_as_b[seeded["post_b"]]["like_count"] == 1

    def test_unliked_post_reports_zero_and_false(self, seeded):
        row = {r["post_id"]: r for r in feed.get_feed(seeded["a"])}[seeded["post_a"]]
        assert row["like_count"] == 0
        assert row["liked_by_me"] is False


class TestCommentAggregation:
    """Acceptance 2: comments ascending with author username."""

    def test_feed_comments_ascending_with_author(self, seeded):
        older = insert_comment(
            seeded["post_b"], seeded["c"], "older", "2026-01-01T01:00:00Z"
        )
        insert_comment(seeded["post_b"], seeded["b"], "newer", "2026-01-01T02:00:00Z")
        row = {r["post_id"]: r for r in feed.get_feed(seeded["a"])}[seeded["post_b"]]
        assert [c["content"] for c in row["comments"]] == ["older", "newer"]
        assert row["comments"][0] == {
            "comment_id": older,
            "parent_id": None,
            "author": "carol",
            "content": "older",
            "created_at": "2026-01-01T01:00:00Z",
            "like_count": 0,
            "liked_by_me": False,
        }
        assert [c["author"] for c in row["comments"]] == ["carol", "bob"]

    def test_comments_same_timestamp_order_by_id_asc(self, seeded):
        insert_comment(seeded["post_b"], seeded["b"], "first", "2026-01-01T01:00:00Z")
        insert_comment(seeded["post_b"], seeded["c"], "second", "2026-01-01T01:00:00Z")
        row = {r["post_id"]: r for r in feed.get_feed(seeded["a"])}[seeded["post_b"]]
        assert [c["content"] for c in row["comments"]] == ["first", "second"]

    def test_post_without_comments_has_empty_list(self, seeded):
        row = {r["post_id"]: r for r in feed.get_feed(seeded["a"])}[seeded["post_a"]]
        assert row["comments"] == []


class TestEmptyFeed:
    """Acceptance 3: no follows and no posts yields []."""

    def test_feed_empty_when_no_follows_and_no_posts(self, interaction_tables):
        a = insert_user("alice")
        assert feed.get_feed(a) == []

    def test_feed_empty_when_followee_has_no_posts(self, interaction_tables):
        a = insert_user("alice")
        b = insert_user("bob")
        add_follow(a, b)
        assert feed.get_feed(a) == []

    def test_feed_unknown_user_returns_empty(self, interaction_tables):
        assert feed.get_feed(999) == []


class TestIndependentVerification:
    """Acceptance 4 / card §6: works with only the card §3.1 DDL applied."""

    def test_feed_creates_likes_comments_tables_when_absent(self, tmp_path, monkeypatch):
        isolated = tmp_path / "isolated.db"
        monkeypatch.setenv(db.DB_PATH_ENV, str(isolated))
        db.init_db()
        db.execute("DROP TABLE IF EXISTS likes")
        db.execute("DROP TABLE IF EXISTS comments")
        assert {"likes", "comments"}.isdisjoint(table_names())

        a = insert_user("alice")
        post = insert_post(a, "hello", "2026-01-01T00:00:00Z")
        with contextlib.closing(db.get_connection()) as conn:
            conn.executescript(INTERACTION_SCHEMA)
        assert {"likes", "comments"} <= table_names()

        insert_like(a, post)
        insert_comment(post, a, "nice", "2026-01-01T00:01:00Z")
        rows = feed.get_feed(a)
        assert len(rows) == 1
        assert rows[0]["like_count"] == 1
        assert rows[0]["liked_by_me"] is True
        assert rows[0]["comments"][0]["content"] == "nice"

    def test_feed_row_contract_shape_and_types(self, seeded):
        rows = feed.get_feed(seeded["a"])
        assert len(rows) == 2
        for row in rows:
            assert set(row) == {
                "post_id",
                "author_id",
                "username",
                "content",
                "created_at",
                "like_count",
                "liked_by_me",
                "comments",
            }
            assert type(row["post_id"]) is int
            assert type(row["author_id"]) is int
            assert type(row["username"]) is str
            assert type(row["content"]) is str
            assert type(row["created_at"]) is str
            assert type(row["like_count"]) is int
            assert type(row["liked_by_me"]) is bool
            assert type(row["comments"]) is list
