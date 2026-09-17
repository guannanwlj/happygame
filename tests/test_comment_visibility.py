"""FP-003 tests: comment visibility pure function (social_app.comment_visibility).

Scenarios documented in docs/test-cases/fp003-comment-visibility.md (groups
A–C). Seeds follow card §6: fresh temp DB via SOCIAL_DB + db.init_db(), users
inserted directly, follow graphs via follows.add_follow, failures via
monkeypatched raisers. Comment rows are plain dicts (contract allows
sqlite3.Row too — covered by B7 through a real db query).
"""

import pytest

from social_app import comment_visibility, db
from social_app.comment_visibility import visible_comments
from social_app.follows import add_follow


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file with the schema applied (card §6)."""
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "social_platform.db"))
    db.init_db()


def insert_user(username: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, "hash"),
    )
    return cur.lastrowid


@pytest.fixture
def persons(temp_db):
    """R (reader), P (post author), M (mutual friend), S (stranger), T."""
    ids = {
        "R": insert_user("r"),
        "P": insert_user("p"),
        "M": insert_user("m"),
        "S": insert_user("s"),
        "T": insert_user("t"),
    }
    add_follow(ids["R"], ids["P"])
    add_follow(ids["P"], ids["R"])
    add_follow(ids["M"], ids["R"])
    add_follow(ids["R"], ids["M"])
    add_follow(ids["M"], ids["P"])
    add_follow(ids["P"], ids["M"])
    return ids


def row(comment_id, author_id, parent_id=None, content=None):
    return {
        "comment_id": comment_id,
        "parent_id": parent_id,
        "author_id": author_id,
        "author": f"u{author_id}",
        "content": content or f"c{comment_id}",
        "created_at": f"2026-01-0{comment_id}T00:00:00Z",
    }


def raiser(exc: Exception):
    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


class TestDispatchOwnOrNonMutual:
    """A1–A4: own posts and non-mutual posts return the list unchanged."""

    def test_own_post_returns_same_list(self, persons):
        ids = persons
        comments = [row(1, ids["S"]), row(2, ids["T"])]
        result = visible_comments(ids["R"], ids["R"], comments)
        assert result is comments

    def test_no_relationship_returns_same_list(self, persons):
        ids = persons
        comments = [row(1, ids["S"]), row(2, ids["M"])]
        result = visible_comments(ids["S"], ids["R"], comments)
        assert result is comments

    def test_one_way_follow_returns_same_list(self, persons):
        ids = persons
        add_follow(ids["S"], ids["R"])  # S follows R, R does not follow back
        comments = [row(1, ids["S"]), row(2, ids["T"])]
        result = visible_comments(ids["R"], ids["S"], comments)
        assert result is comments

    def test_empty_input_stays_empty(self, persons):
        ids = persons
        assert visible_comments(ids["P"], ids["R"], []) == []
        assert visible_comments(ids["R"], ids["R"], []) == []


class TestMutualFriendFilter:
    """B1–B8: friend posts keep only the visible set, order preserved."""

    def test_keeps_mutual_friend_drops_stranger(self, persons):
        ids = persons
        comments = [row(1, ids["M"]), row(2, ids["S"]), row(3, ids["M"])]
        result = visible_comments(ids["P"], ids["R"], comments)
        assert [c["comment_id"] for c in result] == [1, 3]

    def test_post_author_rows_visible(self, persons):
        ids = persons
        reply = row(2, ids["P"], parent_id=1)
        comments = [row(1, ids["P"]), reply]
        result = visible_comments(ids["P"], ids["R"], comments)
        assert [c["comment_id"] for c in result] == [1, 2]

    def test_viewer_rows_visible(self, persons):
        ids = persons
        comments = [row(1, ids["R"]), row(2, ids["S"]), row(3, ids["R"])]
        result = visible_comments(ids["P"], ids["R"], comments)
        assert [c["comment_id"] for c in result] == [1, 3]

    def test_reply_judged_independently_of_parent(self, persons):
        ids = persons
        comments = [
            row(1, ids["M"]),
            row(2, ids["S"], parent_id=1),
            row(3, ids["M"], parent_id=1),
        ]
        result = visible_comments(ids["P"], ids["R"], comments)
        assert [c["comment_id"] for c in result] == [1, 3]

    def test_hidden_parent_surviving_reply_kept(self, persons):
        ids = persons
        comments = [row(1, ids["S"]), row(2, ids["M"], parent_id=1)]
        result = visible_comments(ids["P"], ids["R"], comments)
        assert [c["comment_id"] for c in result] == [2]
        assert result[0]["parent_id"] == 1

    def test_all_invisible_yields_empty_list(self, persons):
        ids = persons
        comments = [row(1, ids["S"]), row(2, ids["T"])]
        assert visible_comments(ids["P"], ids["R"], comments) == []

    def test_sqlite_row_shape_supported(self, persons):
        ids = persons
        post = db.execute(
            "INSERT INTO posts (author_id, content) VALUES (?, ?)",
            (ids["P"], "p"),
        ).lastrowid
        for author, content in ((ids["M"], "m"), (ids["S"], "s")):
            db.execute(
                "INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
                (post, author, content),
            )
        rows = db.query_all(
            "SELECT id, author_id, content FROM comments WHERE post_id = ?",
            (post,),
        )
        result = visible_comments(ids["P"], ids["R"], rows)
        assert [r["content"] for r in result] == ["m"]

    def test_subset_preserves_relative_order(self, persons):
        ids = persons
        comments = [
            row(1, ids["M"]),
            row(2, ids["S"]),
            row(3, ids["R"]),
            row(4, ids["T"]),
            row(5, ids["P"]),
        ]
        result = visible_comments(ids["P"], ids["R"], comments)
        assert [c["comment_id"] for c in result] == [1, 3, 5]


class TestFailClosed:
    """C1–C4: judgment failures return [] (prefer showing less)."""

    def test_is_mutual_follow_raising_yields_empty(self, persons, monkeypatch):
        ids = persons
        monkeypatch.setattr(
            comment_visibility, "is_mutual_follow", raiser(RuntimeError("db"))
        )
        assert visible_comments(ids["P"], ids["R"], [row(1, ids["M"])]) == []

    def test_mutual_friend_ids_raising_yields_empty(self, persons, monkeypatch):
        ids = persons
        monkeypatch.setattr(
            comment_visibility, "mutual_friend_ids", raiser(RuntimeError("db"))
        )
        assert visible_comments(ids["P"], ids["R"], [row(1, ids["M"])]) == []

    def test_row_without_author_id_yields_empty(self, persons):
        ids = persons
        broken = {"comment_id": 1, "content": "no author"}
        assert visible_comments(ids["P"], ids["R"], [broken]) == []

    def test_own_post_short_circuits_before_primitives(self, persons, monkeypatch):
        ids = persons
        monkeypatch.setattr(
            comment_visibility, "is_mutual_follow", raiser(RuntimeError("db"))
        )
        monkeypatch.setattr(
            comment_visibility, "mutual_friend_ids", raiser(RuntimeError("db"))
        )
        comments = [row(1, ids["S"])]
        assert visible_comments(ids["R"], ids["R"], comments) is comments
