"""FP-010 tests: 发布帖子 (create post) — social_app/posts.py.

Scenarios documented in docs/test-cases/fp010-create-post.md (task card §7).
Mock isolation per task card §6: fresh temp DB per test (FP-001 real storage),
seed user `alice` inserted directly, login state injected via the session
(FP-003 not merged yet; integration point I-22 swaps in the real auth).
"""

import pytest

from social_app import create_app, db

CONTENT_MAX_LEN = 1000
EMPTY_REASON = "帖子内容不能为空"
TOO_LONG_REASON = "帖子内容不能超过 1000 字符"


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
def alice_id() -> int:
    """Seed the author user `alice` directly (种子直插用户)."""
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("alice", "seed-hash"),
    )
    return cur.lastrowid


@pytest.fixture
def client(alice_id):
    """Test client on a fresh app, logged in as alice via session injection."""
    app = create_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = alice_id
        yield client


def post_count() -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM posts")
    return row["n"]


def post_row(post_id: int):
    return db.query_one("SELECT * FROM posts WHERE id = ?", (post_id,))


# ---- S1: successful post persists author/content/created_at ----

def test_create_post_success_persists_three_fields(client):
    resp = client.post("/posts/new", data={"content": "hello world"})

    assert resp.status_code == 303
    assert resp.headers["Location"].endswith("/posts/new")
    followed = client.get(resp.headers["Location"])
    assert followed.status_code == 200
    assert "已发布" in followed.get_data(as_text=True)

    assert post_count() == 1
    row = post_row(1)
    assert row is not None
    assert row["content"] == "hello world"
    assert row["created_at"]


def test_create_post_author_is_session_user(client, alice_id):
    client.post("/posts/new", data={"content": "作者是我"})
    row = post_row(1)
    assert row["author_id"] == alice_id


# ---- S2: surrounding whitespace is trimmed before saving ----

def test_create_post_trims_surrounding_whitespace(client):
    client.post("/posts/new", data={"content": "  hello  "})
    row = post_row(1)
    assert row["content"] == "hello"


# ---- S3: empty content is rejected with the specific reason ----

@pytest.mark.parametrize("raw", ["", "   ", " \n\t ", "　"])
def test_create_post_empty_content_fails(client, raw):
    resp = client.post("/posts/new", data={"content": raw})

    assert resp.status_code == 422
    assert EMPTY_REASON in resp.get_data(as_text=True)
    assert post_count() == 0


def test_create_post_missing_content_field_fails(client):
    resp = client.post("/posts/new", data={})

    assert resp.status_code == 422
    assert EMPTY_REASON in resp.get_data(as_text=True)
    assert post_count() == 0


# ---- S4: over-length content is rejected with the specific reason ----

def test_create_post_too_long_content_fails(client):
    resp = client.post("/posts/new", data={"content": "x" * (CONTENT_MAX_LEN + 1)})

    assert resp.status_code == 422
    assert TOO_LONG_REASON in resp.get_data(as_text=True)
    assert post_count() == 0


# ---- S5: exactly at the limit succeeds ----

def test_create_post_exactly_max_length_succeeds(client):
    content = "x" * CONTENT_MAX_LEN
    resp = client.post("/posts/new", data={"content": content})

    assert resp.status_code == 303
    row = post_row(1)
    assert row["content"] == content
    assert len(row["content"]) == CONTENT_MAX_LEN


# ---- S6/S7: anonymous access is intercepted with 302 to login ----

def test_anonymous_get_is_redirected_to_login(client):
    anon = create_app().test_client()
    resp = anon.get("/posts/new")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login?next=/posts/new"


def test_anonymous_post_is_redirected_and_persists_nothing(client):
    anon = create_app().test_client()
    resp = anon.post("/posts/new", data={"content": "ghost post"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login?next=/posts/new"
    assert post_count() == 0


# ---- S8: form page renders the composing controls ----

def test_form_page_renders_textarea_submit_and_error_area(client):
    resp = client.get("/posts/new")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="content"' in html
    assert "<textarea" in html
    assert 'type="submit"' in html
    assert "form-error" in html


# ---- S9: no edit/delete entry points anywhere (D-006) ----

def test_no_edit_or_delete_controls_on_form_page(client):
    html = client.get("/posts/new").get_data(as_text=True)
    assert "编辑" not in html
    assert "删除" not in html


def test_no_edit_or_delete_controls_on_result_page(client):
    resp = client.post("/posts/new", data={"content": "done"})
    html = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "编辑" not in html
    assert "删除" not in html


def test_no_edit_or_delete_routes_exist(client):
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/posts/new" in rules
    assert not any("edit" in r or "delete" in r for r in rules)


# ---- S10: length is validated after trimming ----

def test_length_validated_after_trim(client):
    raw = "  " + "x" * CONTENT_MAX_LEN  # 1002 raw chars, 1000 after trim
    resp = client.post("/posts/new", data={"content": raw})

    assert resp.status_code == 303
    assert len(post_row(1)["content"]) == CONTENT_MAX_LEN
