"""FP-018 tests: comment service (social_app.comment_service).

Scenarios documented in docs/test-cases/fp018-comment-service.md. Every test
gets a fresh temporary database file through the SOCIAL_DB environment
variable, initializes the schema and seeds a user plus a post.
"""

import pytest

from social_app import comment_service
from social_app import comments
from social_app import db
from social_app.comment_service import CommentError, add_comment, list_comments

BLANK_MESSAGE = "评论内容不能为空"


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
    """Seed user alice and post P; return ``(alice_id, post_id)``."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("alice", "hash"),
    )
    alice = cur.lastrowid
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (alice, "post"),
    )
    return alice, cur.lastrowid


def comment_rows(post_id: int) -> list:
    return db.query_all(
        "SELECT id, author_id, content FROM comments WHERE post_id = ?"
        " ORDER BY id",
        (post_id,),
    )


class TestAddComment:
    """A1–A3: non-blank content persists and reads back."""

    def test_add_comment_saves_and_reads_back(self, seed):
        alice, post = seed
        comment_id = add_comment(post, alice, "你好")
        assert type(comment_id) is int
        assert comment_id > 0

        rows = list_comments(post)
        assert len(rows) == 1
        assert rows[0]["id"] == comment_id
        assert rows[0]["post_id"] == post
        assert rows[0]["author_id"] == alice
        assert rows[0]["content"] == "你好"

    def test_two_comments_get_increasing_ids(self, seed):
        alice, post = seed
        first = add_comment(post, alice, "one")
        second = add_comment(post, alice, "two")
        assert second > first
        assert [r["content"] for r in list_comments(post)] == ["one", "two"]

    def test_padded_content_is_accepted_and_stored_verbatim(self, seed):
        alice, post = seed
        add_comment(post, alice, "  hi  ")
        assert [r["content"] for r in list_comments(post)] == ["  hi  "]

    def test_add_comment_delegates_to_storage(self, seed, monkeypatch):
        alice, post = seed
        calls = []
        monkeypatch.setattr(
            comments,
            "add_comment",
            lambda p, a, c: calls.append((p, a, c)) or 42,
        )
        assert add_comment(post, alice, "delegated") == 42
        assert calls == [(post, alice, "delegated")]


class TestBlankContent:
    """B1–B6: blank content raises and never reaches storage."""

    @pytest.mark.parametrize("content", ["   ", "\n\t", "", " \n\t "])
    def test_blank_content_raises_and_does_not_write(self, seed, content):
        alice, post = seed
        with pytest.raises(CommentError) as excinfo:
            add_comment(post, alice, content)
        assert str(excinfo.value) == BLANK_MESSAGE
        assert comment_rows(post) == []

    def test_blank_content_after_existing_comment_keeps_row(self, seed):
        alice, post = seed
        add_comment(post, alice, "keep")
        with pytest.raises(CommentError):
            add_comment(post, alice, "   ")
        assert [r["content"] for r in comment_rows(post)] == ["keep"]

    def test_blank_content_never_calls_storage(self, seed, monkeypatch):
        alice, post = seed
        calls = []
        monkeypatch.setattr(
            comments,
            "add_comment",
            lambda p, a, c: calls.append((p, a, c)) or 1,
        )
        with pytest.raises(CommentError):
            add_comment(post, alice, "   ")
        assert calls == []


class TestListComments:
    """C1–C4: ascending order, scoping and empty result."""

    def test_list_comments_ordered_ascending(self, seed):
        alice, post = seed
        for at, content in [
            ("2026-01-01T00:00:02Z", "second"),
            ("2026-01-01T00:00:00Z", "first"),
            ("2026-01-01T00:00:01Z", "middle"),
        ]:
            db.execute(
                "INSERT INTO comments (post_id, author_id, content, created_at)"
                " VALUES (?, ?, ?, ?)",
                (post, alice, content, at),
            )
        assert [r["content"] for r in list_comments(post)] == [
            "first",
            "middle",
            "second",
        ]

    def test_list_comments_tie_break_by_id(self, seed):
        alice, post = seed
        for content in ["a", "b", "c"]:
            db.execute(
                "INSERT INTO comments (post_id, author_id, content, created_at)"
                " VALUES (?, ?, ?, ?)",
                (post, alice, content, "2026-01-01T00:00:00Z"),
            )
        assert [r["content"] for r in list_comments(post)] == ["a", "b", "c"]

    def test_list_comments_scoped_to_post(self, seed):
        alice, post = seed
        cur = db.execute(
            "INSERT INTO posts (author_id, content) VALUES (?, ?)",
            (alice, "other"),
        )
        other = cur.lastrowid
        add_comment(post, alice, "for P")
        add_comment(other, alice, "for Q")
        assert [r["content"] for r in list_comments(post)] == ["for P"]

    def test_list_comments_empty(self, seed):
        _, post = seed
        result = list_comments(post)
        assert result == []
        assert isinstance(result, list)

    def test_list_comments_delegates_to_storage(self, monkeypatch):
        sentinel = [object()]
        monkeypatch.setattr(
            comment_service.comments, "list_comments", lambda p: sentinel
        )
        assert list_comments(7) is sentinel


class TestExceptionContract:
    """D1–D2: CommentError shape and readable message."""

    def test_comment_error_is_exception(self):
        assert issubclass(CommentError, Exception)

    def test_error_message_is_user_facing_chinese(self):
        assert str(CommentError(BLANK_MESSAGE)) == BLANK_MESSAGE


class FakeComments:
    """In-memory stand-in for the FP-016 storage module (card §6)."""

    def __init__(self):
        self.rows = []
        self.next_id = 1

    def add_comment(self, post_id, author_id, content):
        row = {
            "id": self.next_id,
            "post_id": post_id,
            "author_id": author_id,
            "content": content,
        }
        self.rows.append(row)
        self.next_id += 1
        return row["id"]

    def list_comments(self, post_id):
        return [r for r in self.rows if r["post_id"] == post_id]


class TestStorageMocked:
    """E1–E2: works against a mocked storage layer (dependency isolation)."""

    def test_add_and_list_with_mocked_storage(self, monkeypatch):
        fake = FakeComments()
        monkeypatch.setattr(comment_service, "comments", fake)

        comment_id = add_comment(1, 2, "hello")
        assert comment_id == 1
        assert fake.rows[0]["content"] == "hello"
        assert list_comments(1) == fake.rows

    def test_blank_content_does_not_touch_mocked_storage(self, monkeypatch):
        fake = FakeComments()
        monkeypatch.setattr(comment_service, "comments", fake)

        with pytest.raises(CommentError):
            add_comment(1, 2, "   ")
        assert fake.rows == []
