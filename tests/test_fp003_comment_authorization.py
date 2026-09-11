"""FP-003 tests: comment interaction authorization.

Scenarios documented in
docs/test-cases/fp003-comment-interaction-authorization.md.
Every test gets a fresh temporary database file through the SOCIAL_DB
environment variable, initializes the schema, and seeds its own rows.
"""

import pytest

from social_app import db
from social_app import interaction_service


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


def add_comment(post_id: int, author_id: int, content: str = "nice") -> int:
    cur = db.execute(
        "INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
        (post_id, author_id, content),
    )
    return cur.lastrowid


def follow(follower_id: int, followee_id: int) -> None:
    db.execute(
        "INSERT INTO follows (follower_id, followee_id) VALUES (?, ?)",
        (follower_id, followee_id),
    )


def table_counts() -> dict[str, int]:
    """Row count of every user table, so 'no write' covers future tables too."""
    names = [
        row["name"]
        for row in db.query_all(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {
        name: db.query_one(f"SELECT COUNT(*) AS n FROM {name}")["n"]
        for name in names
    }


def schema_snapshot() -> list[tuple[str, str]]:
    """Sorted (name, sql) of every object, so 'no DDL' is proven too."""
    rows = db.query_all(
        "SELECT name, sql FROM sqlite_master ORDER BY name"
    )
    return [(row["name"], row["sql"]) for row in rows]


@pytest.fixture
def seeded():
    """Card §6 canonical seed: author/follower/stranger, p1, c1, follow."""
    author = insert_user("author")
    follower = insert_user("follower")
    stranger = insert_user("stranger")
    post = insert_post(author)
    comment = add_comment(post, author)
    follow(follower, author)
    return {
        "author": author,
        "follower": follower,
        "stranger": stranger,
        "post": post,
        "comment": comment,
    }


class TestAnonymousDenied:
    """Acceptance: an anonymous actor may not interact with an existing comment."""

    def test_anonymous_denied(self, seeded):
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_comment_interaction(
                None, seeded["comment"]
            )
        assert str(excinfo.value) == interaction_service.ANONYMOUS_MESSAGE
        assert table_counts() == before

    def test_anonymous_denied_writes_nothing(self, seeded):
        schema_before = schema_snapshot()
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_comment_interaction(
                None, seeded["comment"]
            )
        assert schema_snapshot() == schema_before
        assert table_counts() == before


class TestStrangerDenied:
    """Acceptance: a logged-in non-author, non-follower is denied."""

    def test_stranger_denied(self, seeded):
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_comment_interaction(
                seeded["stranger"], seeded["comment"]
            )
        assert str(excinfo.value) == interaction_service.FORBIDDEN_MESSAGE
        assert table_counts() == before

    def test_stranger_denied_writes_nothing(self, seeded):
        schema_before = schema_snapshot()
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_comment_interaction(
                seeded["stranger"], seeded["comment"]
            )
        assert schema_snapshot() == schema_before
        assert table_counts() == before


class TestPostAuthorAllowed:
    """Acceptance: the post author may interact with any comment on it."""

    def test_post_author_allowed(self, seeded):
        assert (
            interaction_service.authorize_comment_interaction(
                seeded["author"], seeded["comment"]
            )
            is None
        )

    def test_post_author_allowed_when_comment_by_other(self):
        author = insert_user("author")
        commenter = insert_user("commenter")
        post = insert_post(author)
        comment = add_comment(post, commenter, "great post")
        assert (
            interaction_service.authorize_comment_interaction(author, comment)
            is None
        )


class TestFollowerAllowed:
    """Acceptance: a follower of the post author may interact with the comment."""

    def test_follower_allowed(self, seeded):
        assert (
            interaction_service.authorize_comment_interaction(
                seeded["follower"], seeded["comment"]
            )
            is None
        )

    def test_reverse_follow_does_not_authorize(self):
        """The comment author following the actor grants nothing."""
        author = insert_user("author")
        other = insert_user("other")
        post = insert_post(author)
        comment = add_comment(post, author)
        follow(author, other)
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_comment_interaction(other, comment)


class TestMissingCommentDenied:
    """Acceptance: an unknown comment id is denied before any other check."""

    def test_missing_comment_denied(self, seeded):
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_comment_interaction(
                seeded["stranger"], 9999
            )
        assert str(excinfo.value) == interaction_service.COMMENT_NOT_FOUND_MESSAGE
        assert table_counts() == before

    def test_missing_comment_wins_over_anonymous(self):
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_comment_interaction(None, 9999)
        assert str(excinfo.value) == interaction_service.COMMENT_NOT_FOUND_MESSAGE

    def test_deleted_comment_is_missing(self, seeded):
        db.execute("DELETE FROM comments WHERE id = ?", (seeded["comment"],))
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_comment_interaction(
                seeded["author"], seeded["comment"]
            )
        assert str(excinfo.value) == interaction_service.COMMENT_NOT_FOUND_MESSAGE
        assert table_counts() == before

    def test_missing_comment_writes_nothing(self, seeded):
        schema_before = schema_snapshot()
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_comment_interaction(seeded["author"], 9999)
        assert schema_snapshot() == schema_before
        assert table_counts() == before


class TestContractAndHooks:
    """Public contract and monkeypatch-friendly module-level dependencies."""

    def test_error_is_exception_subclass(self):
        assert issubclass(interaction_service.InteractionError, Exception)

    def test_comment_not_found_message_constant(self):
        assert interaction_service.COMMENT_NOT_FOUND_MESSAGE == "评论不存在"

    def test_returns_none_on_allow(self, seeded):
        result = interaction_service.authorize_comment_interaction(
            seeded["author"], seeded["comment"]
        )
        assert result is None

    def test_delegates_to_post_authorization(self, seeded, monkeypatch):
        calls = []

        def fake(actor_id, post_id):
            calls.append((actor_id, post_id))
            raise interaction_service.InteractionError("denied")

        monkeypatch.setattr(interaction_service, "authorize_interaction", fake)
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_comment_interaction(
                seeded["follower"], seeded["comment"]
            )
        assert str(excinfo.value) == "denied"
        assert calls == [(seeded["follower"], seeded["post"])]

    def test_no_write_path_on_deny(self, seeded, monkeypatch):
        """A denial must never call db.execute (the only write helper)."""

        def _forbidden(*args, **kwargs):
            raise AssertionError("authorize must not write")

        monkeypatch.setattr(db, "execute", _forbidden)
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_comment_interaction(None, seeded["comment"])
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_comment_interaction(
                seeded["stranger"], seeded["comment"]
            )
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_comment_interaction(seeded["author"], 9999)
