"""FP-006 tests: comment like service business rules.

Scenarios documented in docs/test-cases/fp006-comment-like-service.md. FP-001's
real storage backs the service against a fresh temp database (SOCIAL_DB); one
test monkeypatches the storage primitives to prove the service is independently
verifiable when FP-001 is absent.
"""

import pytest

from social_app import comment_like_service, db


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


def insert_comment(author_id: int, content: str = "hello") -> int:
    cur = db.execute(
        "INSERT INTO posts (author_id, content) VALUES (?, ?)",
        (author_id, "seed post"),
    )
    post_id = cur.lastrowid
    cur = db.execute(
        "INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
        (post_id, author_id, content),
    )
    return cur.lastrowid


def seed() -> tuple[int, int, int]:
    """Alice, Bob and a comment authored by Alice (card §6 seed)."""
    alice = insert_user("alice")
    bob = insert_user("bob")
    comment = insert_comment(alice)
    return alice, bob, comment


def comment_like_rows() -> list[tuple[int, int]]:
    return [
        (r["user_id"], r["comment_id"])
        for r in db.query_all(
            "SELECT user_id, comment_id FROM comment_likes ORDER BY id"
        )
    ]


def post_of(comment_id: int) -> int:
    return db.query_one(
        "SELECT post_id FROM comments WHERE id = ?", (comment_id,)
    )["post_id"]


class TestLikeComment:
    """Acceptance 1: like increments and is idempotent."""

    def test_like_increments_count(self):
        _, b, c = seed()
        assert comment_like_service.like_comment(b, c) == 1
        assert comment_like_rows() == [(b, c)]

    def test_duplicate_like_idempotent(self):
        _, b, c = seed()
        assert comment_like_service.like_comment(b, c) == 1
        assert comment_like_service.like_comment(b, c) == 1
        assert comment_like_rows() == [(b, c)]

    def test_repeated_like_does_not_change_existing_total(self):
        a, b, c = seed()
        comment_like_service.like_comment(a, c)
        comment_like_service.like_comment(b, c)
        assert comment_like_service.like_comment(a, c) == 2


class TestUnlikeComment:
    """Acceptance 2: unlike decrements and is idempotent."""

    def test_unlike_decrements_count(self):
        _, b, c = seed()
        comment_like_service.like_comment(b, c)
        assert comment_like_service.unlike_comment(b, c) == 0
        assert comment_like_rows() == []

    def test_unlike_missing_is_idempotent(self):
        _, b, c = seed()
        assert comment_like_service.unlike_comment(b, c) == 0
        assert comment_like_service.unlike_comment(b, c) == 0
        assert comment_like_rows() == []

    def test_unlike_leaves_other_users_like(self):
        a, b, c = seed()
        comment_like_service.like_comment(a, c)
        comment_like_service.like_comment(b, c)
        assert comment_like_service.unlike_comment(a, c) == 1
        assert comment_like_rows() == [(b, c)]


class TestSelfLike:
    """Acceptance 3: self-like allowed (D6)."""

    def test_self_like_allowed(self):
        a, _, c = seed()
        assert comment_like_service.like_comment(a, c) == 1
        assert comment_like_rows() == [(a, c)]


class TestCountCommentLikes:
    """Acceptance 4: transparent count, per comment."""

    def test_count_reflects_multiple_likers_and_removal(self):
        a, b, c = seed()
        comment_like_service.like_comment(a, c)
        assert comment_like_service.count_comment_likes(c) == 1
        comment_like_service.like_comment(b, c)
        assert comment_like_service.count_comment_likes(c) == 2
        comment_like_service.unlike_comment(a, c)
        assert comment_like_service.count_comment_likes(c) == 1

    def test_count_starts_at_zero(self):
        _, _, c = seed()
        assert comment_like_service.count_comment_likes(c) == 0

    def test_count_is_per_comment(self):
        a, _, c1 = seed()
        c2 = insert_comment(a, "second")
        comment_like_service.like_comment(a, c2)
        assert comment_like_service.count_comment_likes(c1) == 0
        assert comment_like_service.count_comment_likes(c2) == 1


class TestIndependenceFromPostLikes:
    """Acceptance 5 and D8: comment and post likes do not affect each other."""

    def test_independent_from_post_likes(self):
        a, b, c = seed()
        post = post_of(c)
        db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (b, post))
        assert comment_like_service.count_comment_likes(c) == 0
        comment_like_service.like_comment(a, c)
        assert comment_like_service.count_comment_likes(c) == 1
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM likes WHERE post_id = ?", (post,)
        )["n"] == 1


class TestStorageIsolationAndTypes:
    """Edge cases: service verifiable with FP-001 mocked away; int returns."""

    def test_storage_mocked_when_absent(self, monkeypatch):
        store: set[tuple[int, int]] = set()

        def fake_add(user_id, comment_id):
            store.add((user_id, comment_id))
            return True

        def fake_remove(user_id, comment_id):
            existed = (user_id, comment_id) in store
            store.discard((user_id, comment_id))
            return existed

        def fake_count(comment_id):
            return sum(1 for _, cid in store if cid == comment_id)

        monkeypatch.setattr(comment_like_service, "add_comment_like", fake_add)
        monkeypatch.setattr(comment_like_service, "remove_comment_like", fake_remove)
        monkeypatch.setattr(comment_like_service, "count_comment_likes", fake_count)

        assert comment_like_service.like_comment(1, 1) == 1
        assert comment_like_service.like_comment(1, 1) == 1
        assert comment_like_service.unlike_comment(1, 1) == 0

    def test_mutations_and_count_return_int(self):
        _, b, c = seed()
        assert isinstance(comment_like_service.like_comment(b, c), int)
        assert isinstance(comment_like_service.unlike_comment(b, c), int)
        assert isinstance(comment_like_service.count_comment_likes(c), int)
