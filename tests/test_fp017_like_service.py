"""FP-017 tests: like service business rules.

Scenarios documented in docs/test-cases/fp017-like-service.md. FP-015's real
storage backs the service against a fresh temp database (SOCIAL_DB); one test
monkeypatches the storage primitives to prove the service is independently
verifiable when FP-015 is absent.
"""

import pytest

from social_app import db
from social_app import like_service


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


def like_rows() -> list[tuple[int, int]]:
    return [
        (r["user_id"], r["post_id"])
        for r in db.query_all("SELECT user_id, post_id FROM likes ORDER BY id")
    ]


class TestLike:
    """Acceptance 1 & 2: like increments and is idempotent."""

    def test_like_increments_total(self):
        a = insert_user("alice")
        p = insert_post(a)
        assert like_service.like(a, p) == 1
        assert like_rows() == [(a, p)]

    def test_count_grows_with_second_user(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        like_service.like(a, p)
        assert like_service.like(b, p) == 2
        assert like_rows() == [(a, p), (b, p)]

    def test_like_is_idempotent(self):
        a = insert_user("alice")
        p = insert_post(a)
        assert like_service.like(a, p) == 1
        assert like_service.like(a, p) == 1
        assert like_rows() == [(a, p)]

    def test_repeated_like_does_not_change_existing_total(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        like_service.like(a, p)
        like_service.like(b, p)
        assert like_service.like(a, p) == 2


class TestUnlike:
    """Acceptance 3: unlike decrements and is idempotent."""

    def test_unlike_decrements_and_is_idempotent(self):
        a = insert_user("alice")
        p = insert_post(a)
        like_service.like(a, p)
        assert like_service.unlike(a, p) == 0
        assert like_rows() == []
        assert like_service.unlike(a, p) == 0
        assert like_rows() == []

    def test_unlike_leaves_other_users_like(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        like_service.like(a, p)
        like_service.like(b, p)
        assert like_service.unlike(a, p) == 1
        assert like_rows() == [(b, p)]

    def test_unlike_without_prior_like_is_noop(self):
        a = insert_user("alice")
        p = insert_post(a)
        assert like_service.unlike(a, p) == 0
        assert like_rows() == []


class TestCountLikes:
    """Acceptance 4: total per post."""

    def test_count_likes_zero(self):
        a = insert_user("alice")
        p = insert_post(a)
        assert like_service.count_likes(p) == 0

    def test_count_likes_reflects_all_likers(self):
        a, b = insert_user("alice"), insert_user("bob")
        p = insert_post(a)
        like_service.like(a, p)
        like_service.like(b, p)
        assert like_service.count_likes(p) == 2
        assert isinstance(like_service.count_likes(p), int)

    def test_count_likes_is_per_post(self):
        a = insert_user("alice")
        p = insert_post(a, "first")
        q = insert_post(a, "second")
        like_service.like(a, p)
        assert like_service.count_likes(p) == 1
        assert like_service.count_likes(q) == 0


class TestStorageIsolation:
    """Edge case: service verifiable with FP-015 mocked away."""

    def test_storage_mocked_when_absent(self, monkeypatch):
        store: set[tuple[int, int]] = set()

        def fake_add(user_id, post_id):
            store.add((user_id, post_id))
            return True

        def fake_remove(user_id, post_id):
            existed = (user_id, post_id) in store
            store.discard((user_id, post_id))
            return existed

        def fake_count(post_id):
            return sum(1 for _, pid in store if pid == post_id)

        monkeypatch.setattr(like_service, "add_like", fake_add)
        monkeypatch.setattr(like_service, "remove_like", fake_remove)
        monkeypatch.setattr(like_service, "count_likes", fake_count)

        assert like_service.like(1, 1) == 1
        assert like_service.like(1, 1) == 1
        assert like_service.unlike(1, 1) == 0


class TestStorageContractExposure:
    """Card §3.2/§4: storage primitives stay importable from the service."""

    def test_is_liked_reexported_and_reflects_state(self):
        a = insert_user("alice")
        p = insert_post(a)
        assert like_service.is_liked(a, p) is False
        like_service.like(a, p)
        assert like_service.is_liked(a, p) is True
        like_service.unlike(a, p)
        assert like_service.is_liked(a, p) is False
