"""FP-002 tests: mutual friend circle computation.

Scenarios documented in docs/test-cases/fp002-mutual-friend-circle.md. Every
test gets a fresh temporary database file through the SOCIAL_DB environment
variable; follow graphs are built with follows.add_follow and unfollows are
simulated with direct DELETE FROM follows (task card §6).
"""

import pytest

from social_app import db, follows
from social_app.mutual_friends import mutual_friend_ids


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


def make_mutual(a: int, b: int) -> None:
    follows.add_follow(a, b)
    follows.add_follow(b, a)


class TestMutualFriendIncluded:
    """Acceptance 1: mutual friends of both R and P are in the set."""

    def test_mutual_friend_of_both_is_included(self):
        r, p, m = insert_user("reader"), insert_user("author"), insert_user("mutual")
        make_mutual(m, r)
        make_mutual(m, p)
        assert mutual_friend_ids(r, p) == {m}

    def test_multiple_mutual_friends_all_included(self):
        r, p = insert_user("reader"), insert_user("author")
        m, n = insert_user("mutual1"), insert_user("mutual2")
        make_mutual(m, r)
        make_mutual(m, p)
        make_mutual(n, r)
        make_mutual(n, p)
        assert mutual_friend_ids(r, p) == {m, n}


class TestOneSidedMutualExcluded:
    """Acceptance 2: users not mutual with R are excluded."""

    def test_mutual_only_with_author_excluded(self):
        r, p, s = insert_user("reader"), insert_user("author"), insert_user("solo")
        make_mutual(s, p)
        follows.add_follow(s, r)  # S→R exists, R→S missing
        assert s not in mutual_friend_ids(r, p)

    def test_followed_by_reader_only_excluded(self):
        r, p, s = insert_user("reader"), insert_user("author"), insert_user("solo")
        make_mutual(s, p)
        follows.add_follow(r, s)  # R→S exists, S→R missing
        result = mutual_friend_ids(r, p)
        assert result == set()


class TestEmptyWhenNoCommonMutuals:
    """Acceptance 3: R↔P mutual but no shared mutual friends → empty set."""

    def test_mutual_pair_without_common_friends_returns_empty(self):
        r, p = insert_user("reader"), insert_user("author")
        make_mutual(r, p)
        assert mutual_friend_ids(r, p) == set()


class TestReaderAuthorRelationshipIrrelevant:
    """Acceptance 4: set computation ignores whether R and P are mutual."""

    def test_mutual_friend_included_even_when_reader_author_not_mutual(self):
        r, p, m = insert_user("reader"), insert_user("author"), insert_user("mutual")
        make_mutual(m, r)
        make_mutual(m, p)  # no follow rows between r and p at all
        assert mutual_friend_ids(r, p) == {m}


class TestRealTimeRecalculation:
    """Acceptance 5: deleting a follow row immediately shrinks the set."""

    def test_unfollow_removes_user_from_set(self):
        r, p, m = insert_user("reader"), insert_user("author"), insert_user("mutual")
        make_mutual(m, r)
        make_mutual(m, p)
        assert mutual_friend_ids(r, p) == {m}

        db.execute(
            "DELETE FROM follows WHERE follower_id = ? AND followee_id = ?",
            (m, r),
        )
        assert mutual_friend_ids(r, p) == set()


class TestEdgeCases:
    """Edge cases: types, empty inputs, unknown ids, identity, stability."""

    def test_returns_plain_int_set(self):
        r, p, m = insert_user("reader"), insert_user("author"), insert_user("mutual")
        make_mutual(m, r)
        make_mutual(m, p)
        result = mutual_friend_ids(r, p)
        assert type(result) is set
        assert all(type(x) is int for x in result)

    def test_no_follows_at_all_returns_empty(self):
        r, p = insert_user("reader"), insert_user("author")
        assert mutual_friend_ids(r, p) == set()

    def test_unknown_user_ids_return_empty(self):
        r = insert_user("reader")
        assert mutual_friend_ids(r, 9999) == set()

    def test_reader_equals_author_keeps_mutuals_without_self(self):
        r, m = insert_user("reader"), insert_user("mutual")
        make_mutual(m, r)
        assert mutual_friend_ids(r, r) == {m}

    def test_repeated_calls_are_stable(self):
        r, p, m = insert_user("reader"), insert_user("author"), insert_user("mutual")
        make_mutual(m, r)
        make_mutual(m, p)
        first = mutual_friend_ids(r, p)
        second = mutual_friend_ids(r, p)
        assert first == second == {m}

    def test_legacy_friendship_rows_do_not_leak_in(self):
        r, p, m = insert_user("reader"), insert_user("author"), insert_user("legacy")
        db.execute(
            "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (m, r),
        )
        db.execute(
            "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (m, p),
        )
        assert mutual_friend_ids(r, p) == set()
