"""FP-004 tests: visibility rules test matrix (UC-001/UC-002/UC-003).

Checklist-style / parametrized matrix freezing every visible/hidden boundary
of the friend-post comment visibility rules. Scenarios documented in
docs/test-cases/fp004-visibility-matrix.md (groups A-G). Wave-3 start:
FP-001/FP-002/FP-003 are merged, so the real implementations are exercised
directly (task card FP-004 §6 — no shims).

Seeds follow card §6: fresh temp DB via SOCIAL_DB + db.init_db(), users/
follows/posts/comments inserted directly, unfollows via DELETE FROM follows,
fail-closed via monkeypatched raisers, login cookie via create_session.
"""

import pytest

from social_app import comment_visibility, db, feed, views_feed
from social_app.app import Request, create_app
from social_app.comment_visibility import visible_comments
from social_app.follows import add_follow
from social_app.mutual_friends import mutual_friend_ids
from social_app.mutual_follows import is_mutual_follow
from social_app.session import create_session

COMMENT_KEYS = {
    "comment_id",
    "parent_id",
    "author",
    "content",
    "created_at",
    "like_count",
    "liked_by_me",
}

# Friend-post visible set = mutual friends of R and P ∪ {P, R}.
VISIBLE_AUTHORS = ("M", "M2", "P", "R")
# N = mutual with R only, O = mutual with P only (set edge: "both" required);
# S = stranger, T = one-way follower of R, W = one-way followee of R — none of
# the one-way shapes is mutual with both, so all stay outside the set.
HIDDEN_AUTHORS = ("N", "O", "S", "T", "W")

PERSONA_KEYS = VISIBLE_AUTHORS + HIDDEN_AUTHORS


def ts(day: int) -> str:
    """A deterministic comment timestamp (day of 2026-03)."""
    return f"2026-03-{day:02d}T00:00:00Z"


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
    post_id: int, author_id: int, content: str, created_at: str, parent_id=None
) -> int:
    cur = db.execute(
        "INSERT INTO comments (post_id, author_id, content, created_at, parent_id)"
        " VALUES (?, ?, ?, ?, ?)",
        (post_id, author_id, content, created_at, parent_id),
    )
    return cur.lastrowid


def delete_follow(follower_id: int, followee_id: int) -> None:
    db.execute(
        "DELETE FROM follows WHERE follower_id = ? AND followee_id = ?",
        (follower_id, followee_id),
    )


def raiser(exc: Exception):
    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


@pytest.fixture
def world(temp_db):
    """Seed factory (card §4): persona group + follow graph + dispatch posts.

    R reader; P friend author (R↔P); M/M2 mutual with both R and P; N mutual
    with R only; O mutual with P only; S stranger; T one-way follower of R;
    W one-way followee of R (non-mutual author). Posts: friend/own/oneway —
    all three land in R's feed.
    """
    ids = {key: insert_user(key.lower()) for key in PERSONA_KEYS}

    def mutual(a: str, b: str) -> None:
        add_follow(ids[a], ids[b])
        add_follow(ids[b], ids[a])

    mutual("R", "P")
    mutual("M", "R")
    mutual("M", "P")
    mutual("M2", "R")
    mutual("M2", "P")
    mutual("N", "R")  # reader-side friend only
    mutual("O", "P")  # author-side friend only
    add_follow(ids["T"], ids["R"])  # one-way follower of the reader
    add_follow(ids["R"], ids["W"])  # one-way followee of the reader
    ids["friend_post"] = insert_post(ids["P"], "friend-post", ts(1))
    ids["own_post"] = insert_post(ids["R"], "own-post", ts(2))
    ids["oneway_post"] = insert_post(ids["W"], "oneway-post", ts(3))
    return ids


@pytest.fixture
def seeded_comments(world):
    """A fixed comment tree on the friend post: top-level rows from every
    persona plus replies under a visible and under a hidden parent, with
    deterministic created_at order."""
    ids = world
    post = ids["friend_post"]
    m_top = insert_comment(post, ids["M"], "m-top", ts(10))
    insert_comment(post, ids["M2"], "m2-top", ts(11))
    p_top = insert_comment(post, ids["P"], "p-top", ts(12))
    insert_comment(post, ids["R"], "r-top", ts(13))
    insert_comment(post, ids["N"], "n-top", ts(14))
    s_top = insert_comment(post, ids["S"], "s-top", ts(15))
    insert_comment(post, ids["T"], "t-top", ts(16))
    insert_comment(post, ids["S"], "s-reply-under-m", ts(17), parent_id=m_top)
    insert_comment(post, ids["M"], "m-reply-under-s", ts(18), parent_id=s_top)
    insert_comment(post, ids["R"], "r-reply-under-p", ts(19), parent_id=p_top)
    insert_comment(post, ids["S"], "s-reply-under-s", ts(20), parent_id=s_top)
    return {"p_top": p_top, "s_top": s_top}


def comments_for(world, post_id: int, viewer_key: str = "R") -> list[dict]:
    """Return one post's filtered comment dicts from the viewer's feed."""
    rows = {row["post_id"]: row for row in feed.get_feed(world[viewer_key])}
    return rows[post_id]["comments"]


def contents_for(world, post_id: int, viewer_key: str = "R") -> list[str]:
    return [entry["content"] for entry in comments_for(world, post_id, viewer_key)]


def login_root(app, user_id: int):
    """Dispatch a logged-in GET / for ``user_id`` (card §3.2 cookie surface)."""
    token = create_session(user_id)
    return app.dispatch(Request(method="GET", path="/", cookies={"session": token}))


class TestVisibleSetMatrix:
    """A1–A10 (UC-001): the friend post keeps exactly the visible set."""

    @pytest.mark.parametrize("key", VISIBLE_AUTHORS)
    def test_visible_set_member_shown(self, world, key):
        insert_comment(world["friend_post"], world[key], f"{key}-matrix", ts(10))
        assert contents_for(world, world["friend_post"]) == [f"{key}-matrix"]

    @pytest.mark.parametrize("key", HIDDEN_AUTHORS)
    def test_non_visible_author_hidden(self, world, key):
        insert_comment(world["friend_post"], world[key], f"{key}-matrix", ts(10))
        assert contents_for(world, world["friend_post"]) == []

    def test_golden_snapshot_full_tree(self, world, seeded_comments):
        comments = comments_for(world, world["friend_post"])
        assert [entry["content"] for entry in comments] == [
            "m-top",
            "m2-top",
            "p-top",
            "r-top",
            "m-reply-under-s",
            "r-reply-under-p",
        ]
        for entry in comments:
            assert set(entry) == COMMENT_KEYS
        # The promoted reply keeps pointing at its hidden parent; the split
        # lifts it to top level and nests the one visible reply.
        promoted = comments[4]
        assert promoted["parent_id"] == seeded_comments["s_top"]
        tops, replies_by_parent = views_feed._split_comments(comments)
        assert [entry["content"] for entry in tops] == [
            "m-top",
            "m2-top",
            "p-top",
            "r-top",
            "m-reply-under-s",
        ]
        assert set(replies_by_parent) == {seeded_comments["p_top"]}
        assert [
            entry["content"] for entry in replies_by_parent[seeded_comments["p_top"]]
        ] == ["r-reply-under-p"]


DISPATCH_CASES = [
    ("friend_post", "M", True),
    ("friend_post", "S", False),
    ("friend_post", "T", False),
    ("own_post", "S", True),
    ("own_post", "T", True),
    ("own_post", "M", True),
    ("oneway_post", "S", True),
    ("oneway_post", "T", True),
    ("oneway_post", "M", True),
]


class TestDispatchMatrix:
    """B1–B10 (UC-002/UC-003 contrast): own post and one-way post stay full,
    the friend post filters, an unfollow falls back in real time."""

    @pytest.mark.parametrize(("post_key", "author_key", "expected"), DISPATCH_CASES)
    def test_context_author_cell(self, world, post_key, author_key, expected):
        content = f"{author_key}-on-{post_key}"
        insert_comment(world[post_key], world[author_key], content, ts(10))
        assert (content in contents_for(world, world[post_key])) is expected

    def test_no_relationship_returns_identity(self, world):
        rows = [
            {"author_id": world["S"], "content": "s"},
            {"author_id": world["M"], "content": "m"},
        ]
        assert visible_comments(world["S"], world["R"], rows) is rows

    def test_unfollow_falls_back_then_refilters(self, world):
        ids = world
        insert_comment(ids["friend_post"], ids["S"], "s-fallback", ts(10))
        assert contents_for(ids, ids["friend_post"]) == []
        # Delete P→R (R still follows P, so the post stays in the feed): the
        # pair stops being mutual and the post reverts to unfiltered.
        delete_follow(ids["P"], ids["R"])
        assert contents_for(ids, ids["friend_post"]) == ["s-fallback"]
        add_follow(ids["P"], ids["R"])
        assert contents_for(ids, ids["friend_post"]) == []


REPLY_CASES = [
    # (parent author, reply author, parent visible, reply visible)
    ("M", "M", True, True),
    ("M", "R", True, True),
    ("M", "S", True, False),
    ("S", "M", False, True),
    ("S", "R", False, True),
    ("S", "S", False, False),
]


class TestReplyMatrix:
    """C1–C6 (UC-001): replies are judged row by row; a hidden parent leaves
    its visible replies behind, promoted by the renderer's split."""

    @pytest.mark.parametrize(
        ("parent_key", "reply_key", "parent_visible", "reply_visible"), REPLY_CASES
    )
    def test_parent_reply_cell(
        self, world, parent_key, reply_key, parent_visible, reply_visible
    ):
        ids = world
        parent = insert_comment(
            ids["friend_post"], ids[parent_key], f"{parent_key}-parent", ts(10)
        )
        insert_comment(
            ids["friend_post"], ids[reply_key], f"{reply_key}-reply", ts(11),
            parent_id=parent,
        )
        comments = comments_for(ids, ids["friend_post"])
        contents = [entry["content"] for entry in comments]
        assert (f"{parent_key}-parent" in contents) is parent_visible
        assert (f"{reply_key}-reply" in contents) is reply_visible
        tops, replies_by_parent = views_feed._split_comments(comments)
        if parent_visible and reply_visible:
            assert [entry["content"] for entry in tops] == [f"{parent_key}-parent"]
            nested = replies_by_parent.get(parent, [])
            assert [entry["content"] for entry in nested] == [f"{reply_key}-reply"]
        elif parent_visible:
            assert [entry["content"] for entry in tops] == [f"{parent_key}-parent"]
            assert replies_by_parent == {}
        elif reply_visible:
            assert [entry["content"] for entry in tops] == [f"{reply_key}-reply"]
            assert replies_by_parent == {}
        else:
            assert comments == []


class TestEmptyState:
    """D1–D3: filtered-to-empty and zero-comment posts show 暂无评论."""

    def test_all_hidden_comments_filter_to_empty(self, world):
        ids = world
        insert_comment(ids["friend_post"], ids["S"], "s-only", ts(10))
        insert_comment(ids["friend_post"], ids["T"], "t-only", ts(11))
        assert comments_for(ids, ids["friend_post"]) == []

    def test_zero_comment_post_stays_empty(self, world):
        assert comments_for(world, world["friend_post"]) == []

    def test_filtered_to_empty_renders_comments_empty(self, app, world):
        insert_comment(world["friend_post"], world["S"], "s-only", ts(10))
        body = login_root(app, world["R"]).body
        assert '<p class="comments-empty">暂无评论</p>' in body
        assert "s-only" not in body

    def test_per_post_isolation_in_one_feed(self, world):
        ids = world
        insert_comment(ids["friend_post"], ids["S"], "s-hidden", ts(10))
        insert_comment(ids["own_post"], ids["S"], "s-shown-own", ts(11))
        assert comments_for(ids, ids["friend_post"]) == []
        assert contents_for(ids, ids["own_post"]) == ["s-shown-own"]


class TestFailClosed:
    """E1–E3: judgment failures empty every post that needs the judgment —
    never the own post, which short-circuits before the primitives."""

    def test_raising_is_mutual_follow_empties_every_judged_post(
        self, world, monkeypatch
    ):
        ids = world
        insert_comment(ids["friend_post"], ids["M"], "m-c", ts(10))
        insert_comment(ids["own_post"], ids["S"], "s-own", ts(11))
        insert_comment(ids["oneway_post"], ids["S"], "s-oneway", ts(12))
        monkeypatch.setattr(
            comment_visibility, "is_mutual_follow", raiser(RuntimeError("db"))
        )
        # Own post short-circuits before the primitives and stays full; every
        # post that needs the mutual judgment fails closed.
        assert comments_for(ids, ids["friend_post"]) == []
        assert comments_for(ids, ids["oneway_post"]) == []
        assert contents_for(ids, ids["own_post"]) == ["s-own"]

    def test_raising_mutual_friend_ids_empties_friend_post(self, world, monkeypatch):
        ids = world
        insert_comment(ids["friend_post"], ids["M"], "m-c", ts(10))
        monkeypatch.setattr(
            comment_visibility, "mutual_friend_ids", raiser(RuntimeError("db"))
        )
        assert comments_for(ids, ids["friend_post"]) == []

    def test_http_fail_closed_renders_empty_state_per_post(
        self, app, world, monkeypatch
    ):
        ids = world
        insert_comment(ids["friend_post"], ids["M"], "m-c", ts(10))
        insert_comment(ids["own_post"], ids["S"], "s-own", ts(11))
        # One-way post with a comment: its dispatch never reaches the set
        # computation, so it stays the non-empty control and the empty state
        # is uniquely attributable to the failed friend post.
        insert_comment(ids["oneway_post"], ids["T"], "t-oneway", ts(12))
        monkeypatch.setattr(
            comment_visibility, "mutual_friend_ids", raiser(RuntimeError("db"))
        )
        body = login_root(app, ids["R"]).body
        assert '<p class="comments-empty">暂无评论</p>' in body
        assert "m-c" not in body
        assert "s-own" in body
        assert "t-oneway" in body


class TestPrimitiveRealTime:
    """F1–F4 (card §7.3): the FP-001/FP-002 primitives recompute on every
    call — no snapshot — and the change propagates through the filter."""

    def test_is_mutual_follow_flips_on_unfollow_and_refollow(self, world):
        ids = world
        assert is_mutual_follow(ids["P"], ids["R"]) is True
        delete_follow(ids["P"], ids["R"])
        assert is_mutual_follow(ids["P"], ids["R"]) is False
        add_follow(ids["P"], ids["R"])
        assert is_mutual_follow(ids["P"], ids["R"]) is True

    def test_is_mutual_follow_breaks_from_either_direction(self, world):
        ids = world
        delete_follow(ids["R"], ids["P"])
        assert is_mutual_follow(ids["P"], ids["R"]) is False

    def test_mutual_friend_ids_tracks_follow_changes(self, world):
        ids = world
        assert mutual_friend_ids(ids["R"], ids["P"]) == {ids["M"], ids["M2"]}
        delete_follow(ids["M"], ids["P"])
        assert mutual_friend_ids(ids["R"], ids["P"]) == {ids["M2"]}
        add_follow(ids["M"], ids["P"])
        assert mutual_friend_ids(ids["R"], ids["P"]) == {ids["M"], ids["M2"]}
        delete_follow(ids["R"], ids["M2"])  # reader-side break shrinks it too
        circle = mutual_friend_ids(ids["R"], ids["P"])
        assert circle == {ids["M"]}
        assert ids["N"] not in circle  # mutual with R only: never in
        assert ids["O"] not in circle  # mutual with P only: never in

    def test_circle_change_refilters_comments_in_real_time(self, world):
        ids = world
        insert_comment(ids["friend_post"], ids["M"], "m-live", ts(10))
        assert contents_for(ids, ids["friend_post"]) == ["m-live"]
        delete_follow(ids["M"], ids["P"])  # M leaves the R-P circle
        assert contents_for(ids, ids["friend_post"]) == []
        add_follow(ids["M"], ids["P"])  # M rejoins
        assert contents_for(ids, ids["friend_post"]) == ["m-live"]


class TestFeedPageMatrix:
    """G1–G5: black-box GET / renders exactly the visible set."""

    def test_body_shows_exactly_the_visible_set(self, app, world):
        ids = world
        for key in PERSONA_KEYS:
            insert_comment(ids["friend_post"], ids[key], f"{key}-body", ts(10))
        body = login_root(app, ids["R"]).body
        for key in VISIBLE_AUTHORS:
            assert f"{key}-body" in body, key
        for key in HIDDEN_AUTHORS:
            assert f"{key}-body" not in body, key

    def test_hidden_parent_reply_promoted_to_top_level(self, app, world):
        ids = world
        s_top = insert_comment(ids["friend_post"], ids["S"], "s-parent", ts(10))
        insert_comment(
            ids["friend_post"], ids["M"], "m-promoted", ts(11), parent_id=s_top
        )
        body = login_root(app, ids["R"]).body
        assert "m-promoted" in body
        assert "s-parent" not in body
        assert '<li class="comment reply">' not in body
        assert '<li class="comment">' in body

    def test_visible_parent_renders_only_visible_replies(self, app, world):
        ids = world
        m_top = insert_comment(ids["friend_post"], ids["M"], "m-parent", ts(10))
        insert_comment(
            ids["friend_post"], ids["S"], "s-reply-hidden", ts(11), parent_id=m_top
        )
        insert_comment(
            ids["friend_post"], ids["M"], "m-reply-shown", ts(12), parent_id=m_top
        )
        body = login_root(app, ids["R"]).body
        assert "m-parent" in body
        assert "m-reply-shown" in body
        assert "s-reply-hidden" not in body
        assert body.count('<li class="comment reply">') == 1
        assert '<ul class="reply-list">' in body

    def test_anonymous_request_redirects_to_login(self, app, world):
        response = app.dispatch(Request(method="GET", path="/"))
        assert response.status == 303
        assert response.headers["Location"] == "/login"
