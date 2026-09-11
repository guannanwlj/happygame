"""FP-019 tests: interaction authorization guard.

Scenarios documented in docs/test-cases/fp019-interaction-authorization.md.
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


class TestAuthorAuthorized:
    """Acceptance 1: the author may always interact with their own post."""

    def test_author_authorized(self):
        a = insert_user("alice")
        p = insert_post(a)
        assert interaction_service.authorize_interaction(a, p) is None

    def test_author_authorized_with_unrelated_rows(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        insert_post(b, "other")
        follow(b, a)
        assert interaction_service.authorize_interaction(a, p) is None


class TestFollowerAuthorized:
    """Acceptance 2: a follower may interact with the followee's post."""

    def test_follower_authorized(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(b)
        follow(a, b)
        assert interaction_service.authorize_interaction(a, p) is None

    def test_author_also_follows_other_author(self):
        a, b = insert_user("alice"), insert_user("bob")
        own = insert_post(a)
        other = insert_post(b)
        follow(a, b)
        assert interaction_service.authorize_interaction(a, own) is None
        assert interaction_service.authorize_interaction(a, other) is None


class TestUnfollowedNonAuthorDenied:
    """Acceptance 3: no follow and not the author -> denied, no writes."""

    def test_unfollowed_non_author_denied_no_write(self):
        a, c = insert_user("alice"), insert_user("carol")
        p = insert_post(c)
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_interaction(a, p)
        assert str(excinfo.value) == "无权互动该帖子"
        assert table_counts() == before

    def test_denied_with_likes_and_follows_present(self):
        a, c = insert_user("alice"), insert_user("carol")
        p = insert_post(c)
        follow(a, insert_user("dave"))
        db.execute(
            "INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (c, p)
        )
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_interaction(a, p)
        assert table_counts() == before

    def test_follow_direction_does_not_authorize(self):
        """A follows B does not let B act on A's post."""
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        follow(a, b)
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_interaction(b, p)

    def test_following_someone_else_does_not_authorize(self):
        a, c, d = insert_user("alice"), insert_user("carol"), insert_user("dave")
        follow(a, c)
        p = insert_post(d)
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_interaction(a, p)


class TestMissingPostDenied:
    """Acceptance 4: an unknown post id is denied without writes."""

    def test_missing_post_denied_no_write(self):
        a = insert_user("alice")
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_interaction(a, 9999)
        assert str(excinfo.value) == "帖子不存在"
        assert table_counts() == before

    def test_deleted_post_is_missing(self):
        a = insert_user("alice")
        p = insert_post(a)
        db.execute("DELETE FROM posts WHERE id = ?", (p,))
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_interaction(a, p)
        assert str(excinfo.value) == "帖子不存在"
        assert table_counts() == before


class TestAnonymousActor:
    """Anonymous actors are rejected defensively, even before any write."""

    def test_anonymous_denied(self):
        b = insert_user("bob")
        p = insert_post(b)
        before = table_counts()
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_interaction(None, p)
        assert str(excinfo.value) == "未登录"
        assert table_counts() == before

    def test_missing_post_wins_over_anonymous(self):
        """Card order: post lookup precedes the login check."""
        with pytest.raises(interaction_service.InteractionError) as excinfo:
            interaction_service.authorize_interaction(None, 9999)
        assert str(excinfo.value) == "帖子不存在"


class TestContractAndHooks:
    """Public contract and monkeypatch-friendly module-level dependencies."""

    def test_error_is_exception_subclass(self):
        assert issubclass(interaction_service.InteractionError, Exception)

    def test_module_level_is_following_is_patchable(self, monkeypatch):
        a, c = insert_user("alice"), insert_user("carol")
        p = insert_post(c)
        monkeypatch.setattr(interaction_service, "is_following", lambda *_: True)
        assert interaction_service.authorize_interaction(a, p) is None

    def test_no_write_path_on_allow_or_deny(self, monkeypatch):
        """The guard must never call db.execute (the only write helper)."""
        a, b, c = (
            insert_user("alice"),
            insert_user("bob"),
            insert_user("carol"),
        )
        own = insert_post(a)
        followed = insert_post(b)
        denied = insert_post(c)
        follow(a, b)

        def _forbidden(*args, **kwargs):
            raise AssertionError("authorize_interaction must not write")

        monkeypatch.setattr(db, "execute", _forbidden)
        assert interaction_service.authorize_interaction(a, own) is None
        assert interaction_service.authorize_interaction(a, followed) is None
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_interaction(a, denied)
        with pytest.raises(interaction_service.InteractionError):
            interaction_service.authorize_interaction(a, 9999)
