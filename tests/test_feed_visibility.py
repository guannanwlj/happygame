"""FP-003 tests: comment visibility wiring in the feed convergence point.

Scenarios documented in docs/test-cases/fp003-comment-visibility.md (groups
D–E): `feed.get_feed` / `feed._comments` dispatch and end-to-end `GET /`
rendering, promotion of orphaned replies through `views_feed._split_comments`,
the empty state, the real-time fallback after an unfollow, fail-closed
behavior and the anonymous login redirect. Seeds follow card §6.
"""

import pytest

from social_app import comment_visibility, db, feed, views_feed
from social_app.app import Request, create_app
from social_app.follows import add_follow
from social_app.session import create_session

FEED_ROW_KEYS = {
    "post_id",
    "author_id",
    "username",
    "content",
    "created_at",
    "like_count",
    "liked_by_me",
    "comments",
}


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file with the schema applied (card §6)."""
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "social_platform.db"))
    db.init_db()


@pytest.fixture()
def app():
    """A fresh app with the real feed route mounted."""
    return create_app()


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


@pytest.fixture
def persons(temp_db):
    """R (reader), P (friend author), M (mutual friend), S (stranger), T."""
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


@pytest.fixture
def friend_post(persons):
    """P's post visible in R's feed (R follows P); no comments yet."""
    return insert_post(persons["P"], "friend post", "2026-01-01T00:00:00Z")


def feed_row(user_id: int, post_id: int) -> dict:
    rows = {row["post_id"]: row for row in feed.get_feed(user_id)}
    return rows[post_id]


def login_root(app, user_id: int):
    token = create_session(user_id)
    request = Request(method="GET", path="/", cookies={"session": token})
    return app.dispatch(request)


class TestFriendPostFilter:
    """D1–D6: mutual-friend posts filter to the visible set, in order."""

    def test_mutual_friend_kept_stranger_hidden_order_kept(self, persons, friend_post):
        ids = persons
        insert_comment(friend_post, ids["M"], "m-first", "2026-01-02T00:00:00Z")
        s = insert_comment(friend_post, ids["S"], "s-hidden", "2026-01-03T00:00:00Z")
        insert_comment(friend_post, ids["M"], "m-second", "2026-01-04T00:00:00Z")
        comments = feed_row(ids["R"], friend_post)["comments"]
        assert [c["content"] for c in comments] == ["m-first", "m-second"]
        assert s not in [c["comment_id"] for c in comments]
        for entry in comments:
            assert set(entry) == {
                "comment_id",
                "parent_id",
                "author",
                "content",
                "created_at",
                "like_count",
                "liked_by_me",
            }

    def test_post_author_comment_and_reply_visible(self, persons, friend_post):
        ids = persons
        top = insert_comment(friend_post, ids["P"], "p-top", "2026-01-02T00:00:00Z")
        insert_comment(
            friend_post, ids["P"], "p-reply", "2026-01-03T00:00:00Z", parent_id=top
        )
        comments = feed_row(ids["R"], friend_post)["comments"]
        assert [c["content"] for c in comments] == ["p-top", "p-reply"]
        assert comments[1]["parent_id"] == top

    def test_viewer_own_comment_visible(self, persons, friend_post):
        ids = persons
        insert_comment(friend_post, ids["R"], "r-own", "2026-01-02T00:00:00Z")
        comments = feed_row(ids["R"], friend_post)["comments"]
        assert [c["author"] for c in comments] == ["r"]

    def test_reply_judged_independently_of_parent(self, persons, friend_post):
        ids = persons
        top = insert_comment(friend_post, ids["M"], "m-top", "2026-01-02T00:00:00Z")
        insert_comment(
            friend_post, ids["S"], "s-reply-hidden", "2026-01-03T00:00:00Z",
            parent_id=top,
        )
        m_reply = insert_comment(
            friend_post, ids["M"], "m-reply", "2026-01-04T00:00:00Z", parent_id=top
        )
        comments = feed_row(ids["R"], friend_post)["comments"]
        assert [c["comment_id"] for c in comments] == [top, m_reply]

    def test_hidden_parent_reply_promoted_by_split(self, persons, friend_post):
        ids = persons
        s_top = insert_comment(friend_post, ids["S"], "s-top", "2026-01-02T00:00:00Z")
        m_reply = insert_comment(
            friend_post, ids["M"], "m-orphan", "2026-01-03T00:00:00Z", parent_id=s_top
        )
        comments = feed_row(ids["R"], friend_post)["comments"]
        assert [c["comment_id"] for c in comments] == [m_reply]
        tops, replies_by_parent = views_feed._split_comments(comments)
        assert [entry["comment_id"] for entry in tops] == [m_reply]
        assert replies_by_parent == {}

    def test_all_invisible_comments_yield_empty_list(self, persons, friend_post):
        ids = persons
        insert_comment(friend_post, ids["S"], "s-1", "2026-01-02T00:00:00Z")
        insert_comment(friend_post, ids["T"], "t-2", "2026-01-03T00:00:00Z")
        assert feed_row(ids["R"], friend_post)["comments"] == []


class TestStatusQuoPaths:
    """D7–D9, D11: own post, one-way follow, unfollow fallback, row contract."""

    def test_own_post_shows_everyone(self, persons):
        ids = persons
        own = insert_post(ids["R"], "own post", "2026-01-01T00:00:00Z")
        insert_comment(own, ids["S"], "s-c", "2026-01-02T00:00:00Z")
        insert_comment(own, ids["T"], "t-c", "2026-01-03T00:00:00Z")
        insert_comment(own, ids["M"], "m-c", "2026-01-04T00:00:00Z")
        comments = feed_row(ids["R"], own)["comments"]
        assert [c["content"] for c in comments] == ["s-c", "t-c", "m-c"]

    def test_one_way_follow_post_shows_stranger(self, persons):
        ids = persons
        stranger_author = insert_user("p2")
        add_follow(ids["R"], stranger_author)  # one-way: p2 does not follow back
        post = insert_post(stranger_author, "p2 post", "2026-01-01T00:00:00Z")
        insert_comment(post, ids["S"], "s-visible", "2026-01-02T00:00:00Z")
        comments = feed_row(ids["R"], post)["comments"]
        assert [c["content"] for c in comments] == ["s-visible"]

    def test_unfollow_falls_back_to_full_comments(self, persons, friend_post):
        ids = persons
        insert_comment(friend_post, ids["S"], "s-back", "2026-01-02T00:00:00Z")
        db.execute(
            "DELETE FROM follows WHERE follower_id = ? AND followee_id = ?",
            (ids["P"], ids["R"]),
        )
        comments = feed_row(ids["R"], friend_post)["comments"]
        assert [c["content"] for c in comments] == ["s-back"]

    def test_feed_row_contract_unchanged(self, persons, friend_post):
        ids = persons
        insert_comment(friend_post, ids["M"], "m-c", "2026-01-02T00:00:00Z")
        row = feed_row(ids["R"], friend_post)
        assert set(row) == FEED_ROW_KEYS
        assert row["author_id"] == ids["P"]


class TestFailClosedWiring:
    """D10: a raising visibility primitive empties that post's comments."""

    def test_raising_primitive_empties_friend_post_comments(
        self, persons, friend_post, monkeypatch
    ):
        ids = persons
        insert_comment(friend_post, ids["M"], "m-c", "2026-01-02T00:00:00Z")
        insert_comment(friend_post, ids["P"], "p-c", "2026-01-03T00:00:00Z")

        def _raise(*_args, **_kwargs):
            raise RuntimeError("relationship data corrupted")

        monkeypatch.setattr(comment_visibility, "is_mutual_follow", _raise)
        assert feed_row(ids["R"], friend_post)["comments"] == []


class TestFeedPageEndToEnd:
    """E1–E4: GET / renders the filtered comment list (or the login redirect)."""

    def test_friend_post_renders_only_mutual_friend(self, app, persons, friend_post):
        ids = persons
        insert_comment(friend_post, ids["M"], "m-shown", "2026-01-02T00:00:00Z")
        insert_comment(friend_post, ids["S"], "s-hidden", "2026-01-03T00:00:00Z")
        response = login_root(app, ids["R"])
        assert response.status == 200
        assert "m-shown" in response.body
        assert "s-hidden" not in response.body

    def test_promoted_reply_renders_at_top_level(self, app, persons, friend_post):
        ids = persons
        s_top = insert_comment(friend_post, ids["S"], "s-top", "2026-01-02T00:00:00Z")
        insert_comment(
            friend_post, ids["M"], "m-promoted", "2026-01-03T00:00:00Z", parent_id=s_top
        )
        body = login_root(app, ids["R"]).body
        assert "m-promoted" in body
        assert "s-top" not in body
        assert '<ul class="reply-list">' not in body

    def test_filtered_to_empty_renders_comments_empty(self, app, persons, friend_post):
        ids = persons
        insert_comment(friend_post, ids["S"], "s-only", "2026-01-02T00:00:00Z")
        body = login_root(app, ids["R"]).body
        assert '<p class="comments-empty">暂无评论</p>' in body
        assert "s-only" not in body

    def test_anonymous_request_redirects_to_login(self, app, persons):
        response = app.dispatch(Request(method="GET", path="/"))
        assert response.status == 303
        assert response.headers["Location"] == "/login"
