"""FP-024 tests: post persistence module (social_app.posts).

Scenarios documented in docs/test-cases/fp024-post-persistence.md. Every test
gets a fresh temporary database file through the SOCIAL_DB environment
variable, initializes the schema, and seeds one user.
"""

import sqlite3

import pytest

from social_app import db
from social_app import posts


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


@pytest.fixture
def user_id():
    """Seed a single user and return its id."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("alice", "hash"),
    )
    return cur.lastrowid


def post_rows() -> list[sqlite3.Row]:
    return db.query_all(
        "SELECT id, author_id, content FROM posts ORDER BY id"
    )


class TestCreatePost:
    """Acceptances 1-2: normal content persists and returns an int id."""

    def test_create_post_persists_row(self, user_id):
        new_id = posts.create_post(user_id, "hello")
        rows = post_rows()
        assert len(rows) == 1
        assert rows[0]["id"] == new_id
        assert rows[0]["author_id"] == user_id
        assert rows[0]["content"] == "hello"

    def test_create_post_returns_int_id(self, user_id):
        result = posts.create_post(user_id, "hello")
        assert type(result) is int
        assert result > 0

    def test_second_post_gets_larger_id(self, user_id):
        first = posts.create_post(user_id, "one")
        second = posts.create_post(user_id, "two")
        assert second > first
        assert [r["content"] for r in post_rows()] == ["one", "two"]

    def test_content_with_surrounding_whitespace_is_stored_unchanged(
        self, user_id
    ):
        posts.create_post(user_id, "  hi  ")
        assert [r["content"] for r in post_rows()] == ["  hi  "]


class TestBlankContent:
    """Acceptance 3: blank content raises PostError and writes nothing."""

    @pytest.mark.parametrize("content", ["   ", "\n\t", "", " \n\t "])
    def test_blank_content_raises_and_does_not_write(self, user_id, content):
        with pytest.raises(posts.PostError):
            posts.create_post(user_id, content)
        assert post_rows() == []

    def test_blank_content_does_not_write_after_existing_row(self, user_id):
        posts.create_post(user_id, "keep")
        with pytest.raises(posts.PostError):
            posts.create_post(user_id, "   ")
        assert len(post_rows()) == 1

    def test_error_message_is_user_facing_chinese(self, user_id):
        with pytest.raises(posts.PostError) as excinfo:
            posts.create_post(user_id, "   ")
        assert str(excinfo.value) == "帖子内容不能为空"


class TestViewsPostContract:
    """Acceptance 4: the module satisfies the FP-012 lazy-import contract."""

    def test_module_exposes_contract_for_views_post(self):
        assert callable(posts.create_post)
        assert issubclass(posts.PostError, Exception)

    def test_views_post_load_posts_resolves_this_module(self):
        from social_app import views_post

        assert views_post._load_posts() is posts

    def test_existing_post_survives_reinit(self, user_id):
        posts.create_post(user_id, "durable")
        db.init_db()
        assert [r["content"] for r in post_rows()] == ["durable"]


class TestIntegrity:
    """Edge cases: foreign-key enforcement stays intact."""

    def test_missing_author_raises_integrity_error(self):
        with pytest.raises(sqlite3.IntegrityError):
            posts.create_post(999, "orphan")
