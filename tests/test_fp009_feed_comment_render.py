"""FP-009 tests: feed comment rendering extensions.

Scenarios documented in docs/test-cases/fp009-feed-comment-render.md. Query tests
seed a fresh temporary database (``SOCIAL_DB``) and apply the card §3.1
``comments.parent_id`` + ``comment_likes`` DDL because FP-001/FP-002 have not
landed (card §6). Render tests monkeypatch ``views_feed.get_feed`` with
contract-shaped stub rows and stub FP-003's guard, so no database is touched.
"""

import contextlib
from types import SimpleNamespace

import pytest

from social_app import db, feed, views_feed
from social_app.app import Request, create_app

COMMENT_INTERACTION_SCHEMA = """
DROP TABLE IF EXISTS comment_likes;
DROP TABLE IF EXISTS comments;
CREATE TABLE comments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id    INTEGER NOT NULL REFERENCES posts(id),
  author_id  INTEGER NOT NULL REFERENCES users(id),
  content    TEXT    NOT NULL,
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  parent_id  INTEGER REFERENCES comments(id)
);
CREATE TABLE comment_likes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  comment_id INTEGER NOT NULL REFERENCES comments(id),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (user_id, comment_id)
);
"""

LEGACY_COMMENT_SCHEMA = """
DROP TABLE IF EXISTS comment_likes;
DROP TABLE IF EXISTS comments;
CREATE TABLE comments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id    INTEGER NOT NULL REFERENCES posts(id),
  author_id  INTEGER NOT NULL REFERENCES users(id),
  content    TEXT    NOT NULL,
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

CONTRACT_KEYS = {
    "comment_id",
    "parent_id",
    "author",
    "content",
    "created_at",
    "like_count",
    "liked_by_me",
}


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file with the base schema applied."""
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "social_platform.db"))
    db.init_db()


@pytest.fixture
def comment_schema(temp_db):
    """Apply the card §3.1 comment reply/like DDL (card §6 mock)."""
    with contextlib.closing(db.get_connection()) as conn:
        conn.executescript(COMMENT_INTERACTION_SCHEMA)


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


def insert_comment(
    post_id: int,
    author_id: int,
    content: str,
    created_at: str,
    parent_id: int | None = None,
) -> int:
    cur = db.execute(
        "INSERT INTO comments (post_id, author_id, content, created_at, parent_id)"
        " VALUES (?, ?, ?, ?, ?)",
        (post_id, author_id, content, created_at, parent_id),
    )
    return cur.lastrowid


def insert_comment_like(user_id: int, comment_id: int, created_at: str) -> int:
    cur = db.execute(
        "INSERT INTO comment_likes (user_id, comment_id, created_at)"
        " VALUES (?, ?, ?)",
        (user_id, comment_id, created_at),
    )
    return cur.lastrowid


@pytest.fixture
def seeded(comment_schema):
    """alice/bob, p1(alice), top-level c1 and reply c2, one like (bob, c1)."""
    alice = insert_user("alice")
    bob = insert_user("bob")
    post = insert_post(alice, "p1", "2026-01-01T00:00:00Z")
    c1 = insert_comment(post, alice, "parent text", "2026-01-02T00:00:00Z")
    c2 = insert_comment(
        post, bob, "reply text", "2026-01-03T00:00:00Z", parent_id=c1
    )
    insert_comment_like(bob, c1, "2026-01-04T00:00:00Z")
    return {
        "alice": alice,
        "bob": bob,
        "post": post,
        "c1": c1,
        "c2": c2,
    }


class TestCommentsQueryContract:
    """A1–A3: the upgraded `_comments` / `get_feed` shape and reply relation."""

    def test_feed_comments_include_parent_id_and_like_data(self, seeded):
        comments = feed._comments(seeded["post"], seeded["alice"])
        by_id = {c["comment_id"]: c for c in comments}
        assert set(by_id) == {seeded["c1"], seeded["c2"]}
        for entry in comments:
            assert set(entry) == CONTRACT_KEYS
        assert by_id[seeded["c1"]]["parent_id"] is None
        assert by_id[seeded["c2"]]["parent_id"] == seeded["c1"]
        assert by_id[seeded["c1"]]["author"] == "alice"
        assert by_id[seeded["c1"]]["like_count"] == 1
        assert by_id[seeded["c1"]]["liked_by_me"] is False

    def test_get_feed_comments_upgraded_too(self, seeded):
        row = {r["post_id"]: r for r in feed.get_feed(seeded["alice"])}[seeded["post"]]
        by_id = {c["comment_id"]: c for c in row["comments"]}
        assert set(by_id) == {seeded["c1"], seeded["c2"]}
        assert by_id[seeded["c2"]]["parent_id"] == seeded["c1"]


class TestCommentLikeData:
    """B1–B3: like_count and viewer-specific liked_by_me."""

    def test_like_count_and_liked_by_me_per_viewer(self, seeded):
        as_bob = {c["comment_id"]: c for c in feed._comments(seeded["post"], seeded["bob"])}
        as_alice = {
            c["comment_id"]: c for c in feed._comments(seeded["post"], seeded["alice"])
        }
        assert as_bob[seeded["c1"]]["like_count"] == 1
        assert as_bob[seeded["c1"]]["liked_by_me"] is True
        assert as_alice[seeded["c1"]]["liked_by_me"] is False
        assert as_alice[seeded["c1"]]["like_count"] == 1

    def test_unliked_comment_reports_zero_and_false(self, seeded):
        entry = {
            c["comment_id"]: c for c in feed._comments(seeded["post"], seeded["bob"])
        }[seeded["c2"]]
        assert entry["like_count"] == 0
        assert entry["liked_by_me"] is False


class TestRepliesAscending:
    """A4: sibling replies ordered `created_at ASC, id ASC`."""

    def test_replies_ascending_by_time_then_id(self, seeded):
        later = insert_comment(
            seeded["post"], seeded["alice"], "later", "2026-01-06T00:00:00Z",
            parent_id=seeded["c1"],
        )
        same_a = insert_comment(
            seeded["post"], seeded["bob"], "same-a", "2026-01-05T00:00:00Z",
            parent_id=seeded["c1"],
        )
        same_b = insert_comment(
            seeded["post"], seeded["alice"], "same-b", "2026-01-05T00:00:00Z",
            parent_id=seeded["c1"],
        )
        comments = feed._comments(seeded["post"], seeded["alice"])
        ordered = [c["comment_id"] for c in comments]
        assert ordered.index(same_a) < ordered.index(same_b) < ordered.index(later)


def comment_entry(
    comment_id,
    parent_id,
    author,
    content,
    created_at,
    like_count=0,
    liked_by_me=False,
):
    return {
        "comment_id": comment_id,
        "parent_id": parent_id,
        "author": author,
        "content": content,
        "created_at": created_at,
        "like_count": like_count,
        "liked_by_me": liked_by_me,
    }


def feed_row(comments, post_id=1):
    return {
        "post_id": post_id,
        "author_id": 9,
        "username": "alice",
        "content": "a post",
        "created_at": "2026-01-01T00:00:00Z",
        "like_count": 0,
        "liked_by_me": False,
        "comments": comments,
    }


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def logged_in(monkeypatch):
    monkeypatch.setattr(views_feed, "require_login", lambda request: None)
    monkeypatch.setattr(views_feed, "current_user_id", lambda request: 7)


def stub_feed(monkeypatch, rows):
    monkeypatch.setattr(views_feed, "get_feed", lambda user_id: rows)


def get_root(app):
    return app.dispatch(Request(method="GET", path="/"))


class TestReplyRendering:
    """C1–C2: replies nest one level under their parent and no deeper."""

    def test_reply_nested_under_parent(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(1, None, "alice", "parent text", "2026-01-02T00:00:00Z"),
                        comment_entry(2, 1, "bob", "reply text", "2026-01-03T00:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert '<ul class="comment-list">' in body
        assert '<ul class="reply-list">' in body
        assert 'class="comment reply"' in body
        assert body.index("parent text") < body.index("reply text")

    def test_replies_are_not_nested_further(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(1, None, "alice", "parent", "2026-01-02T00:00:00Z"),
                        comment_entry(2, 1, "bob", "reply one", "2026-01-03T00:00:00Z"),
                        comment_entry(3, 2, "carol", "reply two", "2026-01-04T00:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert body.count('<ul class="reply-list">') == 1

    def test_replies_render_ascending(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(1, None, "alice", "parent", "2026-01-02T00:00:00Z"),
                        comment_entry(2, 1, "bob", "first reply", "2026-01-03T00:00:00Z"),
                        comment_entry(3, 1, "carol", "second reply", "2026-01-04T00:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert body.index("first reply") < body.index("second reply")


class TestCommentLikeRendering:
    """B4/C6: the viewer's comment-like state is displayed."""

    def test_like_count_and_liked_state_shown(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(
                            1, None, "alice", "c1", "2026-01-02T00:00:00Z",
                            like_count=3, liked_by_me=True,
                        )
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert "3" in body
        assert "已赞" in body

    def test_unliked_state_shown(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [feed_row([comment_entry(1, None, "alice", "c1", "t")])],
        )
        body = get_root(app).body
        assert "未赞" in body


class TestEscaping:
    """C3–C4: every comment field is HTML-escaped."""

    def test_comment_content_escaped(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(
                            1, None, "eve", "<script>alert(1)</script>", "t"
                        )
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    def test_comment_author_and_time_escaped(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [feed_row([comment_entry(1, None, "<b>eve</b>", "hi", "<i>t</i>")])],
        )
        body = get_root(app).body
        assert "<b>eve</b>" not in body
        assert "<i>t</i>" not in body
        assert "&lt;b&gt;eve&lt;/b&gt;" in body
        assert "&lt;i&gt;t&lt;/i&gt;" in body


class TestLegacyShapes:
    """C5–C6/E1: old comment dicts and the legacy schema still work."""

    def test_legacy_comment_shape_renders(self, app, logged_in, monkeypatch):
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        {
                            "author": "eve",
                            "content": "old comment",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                )
            ],
        )
        response = get_root(app)
        assert response.status == 200
        assert "old comment" in response.body
        assert '<ul class="comment-list">' in response.body
        assert '<ul class="reply-list">' not in response.body

    def test_legacy_schema_keeps_legacy_comment_shape(self, seeded):
        with contextlib.closing(db.get_connection()) as conn:
            conn.executescript(LEGACY_COMMENT_SCHEMA)
        db.execute(
            "INSERT INTO comments (post_id, author_id, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (seeded["post"], seeded["alice"], "legacy", "2026-01-05T00:00:00Z"),
        )
        entry = feed._comments(seeded["post"], seeded["alice"])[-1]
        assert entry == {
            "author": "alice",
            "content": "legacy",
            "created_at": "2026-01-05T00:00:00Z",
        }


class TestSiblingHelpers:
    """D1–D4: provided FP-005/FP-007 helpers are used, absent ones fall back."""

    def test_provided_comment_likes_helper_is_used(self, app, logged_in, monkeypatch):
        monkeypatch.setattr(
            views_feed,
            "_render_comment_likes",
            lambda entry: '<div class="real-comment-likes">sentinel</div>',
            raising=False,
        )
        stub_feed(monkeypatch, [feed_row([comment_entry(1, None, "a", "c", "t")])])
        body = get_root(app).body
        assert "real-comment-likes" in body
        assert "comment-liked-state" not in body

    def test_provided_reply_helpers_are_used(self, app, logged_in, monkeypatch):
        monkeypatch.setattr(
            views_feed,
            "_render_reply_form",
            lambda entry: '<form id="reply-form"></form>',
            raising=False,
        )
        monkeypatch.setattr(
            views_feed,
            "_render_replies",
            lambda entry, replies: '<ul class="real-replies"></ul>',
            raising=False,
        )
        stub_feed(
            monkeypatch,
            [
                feed_row(
                    [
                        comment_entry(1, None, "a", "parent", "2026-01-01T00:00:00Z"),
                        comment_entry(2, 1, "b", "reply", "2026-01-02T00:00:00Z"),
                    ]
                )
            ],
        )
        body = get_root(app).body
        assert 'id="reply-form"' in body
        assert "real-replies" in body
        assert "reply-list" not in body

    def test_namespace_contract_row_renders(self, app, logged_in, monkeypatch):
        row = SimpleNamespace(
            post_id=5,
            author_id=1,
            username="alice",
            content="post",
            created_at="2026-01-01T00:00:00Z",
            like_count=0,
            liked_by_me=False,
            comments=[
                SimpleNamespace(
                    comment_id=1,
                    parent_id=None,
                    author="alice",
                    content="nice",
                    created_at="2026-01-02T00:00:00Z",
                    like_count=0,
                    liked_by_me=False,
                ),
                SimpleNamespace(
                    comment_id=2,
                    parent_id=1,
                    author="bob",
                    content="sweet",
                    created_at="2026-01-03T00:00:00Z",
                    like_count=0,
                    liked_by_me=False,
                ),
            ],
        )
        stub_feed(monkeypatch, [row])
        body = get_root(app).body
        assert "nice" in body
        assert "sweet" in body
        assert '<ul class="reply-list">' in body
