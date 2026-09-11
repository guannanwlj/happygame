"""FP-008 tests: reply level and content validation (social_app.reply_service).

Scenarios documented in docs/test-cases/fp008-reply-validation.md. Every test
gets a fresh temporary database file through the SOCIAL_DB environment variable,
initializes the schema and seeds the card §6 fixtures (users alice/bob, post p1,
top-level comment c1, reply c2).
"""

import pytest

from social_app import comments
from social_app import db
from social_app import reply_service
from social_app.reply_service import (
    BLANK_CONTENT_MESSAGE,
    NOT_TOP_LEVEL_MESSAGE,
    PARENT_NOT_FOUND_MESSAGE,
    ReplyError,
    add_reply,
)


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
def seed():
    """Seed the card §6 fixtures; return a dict of ids."""
    alice = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("alice", "hash"),
    ).lastrowid
    bob = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("bob", "hash"),
    ).lastrowid
    post = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (alice, "p1"),
    ).lastrowid
    c1 = comments.add_comment(post, alice, "c1")
    c2 = comments.add_comment(post, bob, "c2", parent_id=c1)
    return {
        "alice": alice,
        "bob": bob,
        "post": post,
        "c1": c1,
        "c2": c2,
    }


def comment_count() -> int:
    return db.query_one("SELECT COUNT(*) AS n FROM comments")["n"]


class TestReplyToTopLevel:
    """Acceptance A: replying to a top-level comment inserts with its parent."""

    def test_reply_to_top_level_inserted_with_parent(self, seed):
        reply_id = add_reply(seed["c1"], seed["bob"], "hi")
        row = comments.get_comment(reply_id)
        assert type(reply_id) is int
        assert reply_id > 0
        assert row["post_id"] == seed["post"]
        assert row["parent_id"] == seed["c1"]
        assert row["author_id"] == seed["bob"]
        assert row["content"] == "hi"

    def test_padded_reply_accepted_and_stored_verbatim(self, seed):
        reply_id = add_reply(seed["c1"], seed["bob"], "  hi  ")
        assert comments.get_comment(reply_id)["content"] == "  hi  "

    def test_two_replies_get_increasing_ids(self, seed):
        first = add_reply(seed["c1"], seed["bob"], "one")
        second = add_reply(seed["c1"], seed["bob"], "two")
        assert second > first

    def test_add_reply_delegates_to_storage(self, seed, monkeypatch):
        calls = []

        def fake_add_comment(post_id, author_id, content, parent_id=None):
            calls.append((post_id, author_id, content, parent_id))
            return 42

        monkeypatch.setattr(comments, "add_comment", fake_add_comment)
        assert add_reply(seed["c1"], seed["bob"], "delegated") == 42
        assert calls == [(seed["post"], seed["bob"], "delegated", seed["c1"])]


class TestReplyToReply:
    """Acceptance B: one level only; reply-to-reply is rejected with no write."""

    def test_reply_to_reply_rejected(self, seed):
        with pytest.raises(ReplyError) as excinfo:
            add_reply(seed["c2"], seed["bob"], "nested")
        assert str(excinfo.value) == NOT_TOP_LEVEL_MESSAGE

    def test_rejection_does_not_write(self, seed):
        before = comment_count()
        with pytest.raises(ReplyError):
            add_reply(seed["c2"], seed["bob"], "nested")
        assert comment_count() == before

    def test_rejection_never_calls_storage(self, seed, monkeypatch):
        calls = []
        monkeypatch.setattr(
            comments,
            "add_comment",
            lambda *a, **k: calls.append((a, k)) or 1,
        )
        with pytest.raises(ReplyError):
            add_reply(seed["c2"], seed["bob"], "nested")
        assert calls == []


class TestMissingParent:
    """Acceptance C: a non-existent parent is rejected with no write."""

    def test_reply_to_missing_parent_rejected(self):
        with pytest.raises(ReplyError) as excinfo:
            add_reply(999, 1, "hi")
        assert str(excinfo.value) == PARENT_NOT_FOUND_MESSAGE

    def test_missing_parent_takes_precedence_over_blank_content(self):
        with pytest.raises(ReplyError) as excinfo:
            add_reply(999, 1, "   ")
        assert str(excinfo.value) == PARENT_NOT_FOUND_MESSAGE

    def test_missing_parent_writes_nothing(self, seed):
        before = comment_count()
        with pytest.raises(ReplyError):
            add_reply(999, seed["bob"], "hi")
        assert comment_count() == before


class TestBlankContent:
    """Acceptance D: blank bodies are rejected with no write."""

    def test_blank_reply_rejected(self, seed):
        before = comment_count()
        with pytest.raises(ReplyError) as excinfo:
            add_reply(seed["c1"], seed["bob"], "  ")
        assert str(excinfo.value) == BLANK_CONTENT_MESSAGE
        assert comment_count() == before

    @pytest.mark.parametrize("content", ["   ", "", "\n\t", " \n\t "])
    def test_blank_variants_rejected(self, seed, content):
        with pytest.raises(ReplyError) as excinfo:
            add_reply(seed["c1"], seed["bob"], content)
        assert str(excinfo.value) == BLANK_CONTENT_MESSAGE

    def test_blank_after_real_reply_keeps_row(self, seed):
        add_reply(seed["c1"], seed["bob"], "keep")
        before = comment_count()
        with pytest.raises(ReplyError):
            add_reply(seed["c1"], seed["bob"], "   ")
        assert comment_count() == before

    def test_rejection_writes_nothing(self, seed):
        before = comment_count()
        for parent, content in [(seed["c1"], "   "), (seed["c2"], "x"), (999, "x")]:
            with pytest.raises(ReplyError):
                add_reply(parent, seed["bob"], content)
        assert comment_count() == before


class TestSelfReply:
    """Acceptance E: replying to your own comment is allowed (D6)."""

    def test_self_reply_allowed(self, seed):
        reply_id = add_reply(seed["c1"], seed["alice"], "mine")
        row = comments.get_comment(reply_id)
        assert row["author_id"] == seed["alice"]
        assert row["parent_id"] == seed["c1"]


class TestExceptionContract:
    """ReplyError shape and readable message."""

    def test_reply_error_is_exception(self):
        assert issubclass(ReplyError, Exception)

    def test_error_message_is_user_facing_chinese(self):
        for message in (
            PARENT_NOT_FOUND_MESSAGE,
            NOT_TOP_LEVEL_MESSAGE,
            BLANK_CONTENT_MESSAGE,
        ):
            assert str(ReplyError(message)) == message


class FakeComments:
    """In-memory stand-in for the FP-002 storage module."""

    def __init__(self):
        self.rows = {}
        self.next_id = 1

    def add_comment(self, post_id, author_id, content, parent_id=None):
        row = {
            "id": self.next_id,
            "post_id": post_id,
            "author_id": author_id,
            "content": content,
            "parent_id": parent_id,
        }
        self.rows[row["id"]] = row
        self.next_id += 1
        return row["id"]

    def get_comment(self, comment_id):
        return self.rows.get(comment_id)


class TestStorageMocked:
    """F: works against a mocked storage layer (dependency isolation)."""

    def test_valid_reply_with_mocked_storage(self, monkeypatch):
        fake = FakeComments()
        fake.add_comment(1, 1, "c1")
        fake.add_comment(1, 2, "c2", parent_id=1)
        monkeypatch.setattr(reply_service, "comments", fake)

        reply_id = add_reply(1, 2, "reply")
        assert reply_id == 3
        assert fake.rows[3]["post_id"] == 1
        assert fake.rows[3]["parent_id"] == 1

    def test_reply_to_reply_does_not_touch_mocked_storage(self, monkeypatch):
        fake = FakeComments()
        fake.add_comment(1, 1, "c1")
        fake.add_comment(1, 2, "c2", parent_id=1)
        monkeypatch.setattr(reply_service, "comments", fake)

        with pytest.raises(ReplyError):
            add_reply(2, 2, "nested")
        assert set(fake.rows) == {1, 2}
