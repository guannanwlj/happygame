"""FP-002 tests: upload validation rules (social_app.posts).

Scenarios documented in docs/test-cases/fp002-upload-validation.md.
Validation is a pure function; create_post tests use a fresh temporary
database via the SOCIAL_DB environment variable (same autouse fixture
pattern as tests/test_fp024_posts.py) plus one seeded user.
"""

import sqlite3

import pytest

from social_app import db
from social_app import posts
from social_app.posts import UploadedImage

PNG_IMG = UploadedImage("a.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)


def sized(name: str, n: int) -> UploadedImage:
    """Build an image whose byte length is exactly ``n``."""
    return UploadedImage(name, b"x" * n)


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path, monkeypatch):
    """Point SOCIAL_DB at a fresh temp file so tests never touch the repo."""
    path = tmp_path / "t.db"
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


class TestImageCount:
    """Acceptance 1: at most 9 images."""

    def test_ten_images_rejected_with_count_message(self):
        imgs = [PNG_IMG] * 10
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("", imgs)
        assert str(excinfo.value) == "图片数量不能超过 9 张"

    def test_exactly_nine_images_pass(self):
        assert posts.validate_post_submission("", [PNG_IMG] * 9) is None


class TestImageFormat:
    """Acceptance 2: extension whitelist JPEG/PNG/WebP."""

    def test_gif_among_valid_images_rejects_whole_submission(self):
        imgs = [PNG_IMG, UploadedImage("a.gif", b"x" * 10), PNG_IMG]
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("hi", imgs)
        assert str(excinfo.value) == "图片格式仅支持 JPEG/PNG/WebP"

    @pytest.mark.parametrize("name", ["a.PNG", "a.JPEG", "b.WebP", "c.JPG"])
    def test_uppercase_extension_passes(self, name):
        assert posts.validate_post_submission("", [sized(name, 8)]) is None

    @pytest.mark.parametrize("name", ["a.txt", "noext", "a.bmp"])
    def test_unknown_or_missing_extension_rejected(self, name):
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("", [sized(name, 8)])
        assert str(excinfo.value) == "图片格式仅支持 JPEG/PNG/WebP"


class TestImageSize:
    """Acceptance 3: per-image 5MB ceiling."""

    def test_five_mb_plus_one_byte_rejected(self):
        imgs = [sized("big.png", posts.MAX_IMAGE_BYTES + 1)]
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("", imgs)
        assert str(excinfo.value) == "单张图片不能超过 5MB"

    def test_exactly_five_mb_passes(self):
        imgs = [sized("edge.png", posts.MAX_IMAGE_BYTES)]
        assert posts.validate_post_submission("", imgs) is None

    def test_second_image_oversize_rejected(self):
        imgs = [PNG_IMG, sized("big.jpg", posts.MAX_IMAGE_BYTES + 1)]
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("hi", imgs)
        assert str(excinfo.value) == "单张图片不能超过 5MB"


class TestBlankContentWithImages:
    """Acceptance 4 (D-1): blank text + >=1 valid image is acceptable."""

    def test_blank_text_with_one_image_passes_validation(self):
        assert posts.validate_post_submission("  ", [PNG_IMG]) is None

    def test_blank_text_with_image_count_writes_pure_image_post(self, user_id):
        new_id = posts.create_post(user_id, "  ", image_count=1)
        rows = post_rows()
        assert len(rows) == 1
        assert rows[0]["id"] == new_id
        assert rows[0]["content"] == "  "
        assert rows[0]["author_id"] == user_id

    def test_blank_text_with_two_images_writes_one_row(self, user_id):
        posts.create_post(user_id, "", image_count=2)
        assert len(post_rows()) == 1


class TestBlankContentWithoutImages:
    """Acceptance 5: blank text + no image stays rejected."""

    def test_blank_text_no_image_fails_validation(self):
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("  ", [])
        assert str(excinfo.value) == "帖子内容不能为空"

    def test_blank_text_default_image_count_still_raises(self, user_id):
        with pytest.raises(posts.PostError):
            posts.create_post(user_id, "  ")
        assert post_rows() == []


class TestTextOnlyRegression:
    """Acceptance 6: text-only posts behave exactly as before."""

    def test_text_only_passes_validation(self):
        assert posts.validate_post_submission("hello", []) is None

    def test_text_only_create_post_unchanged(self, user_id):
        new_id = posts.create_post(user_id, "hello")
        rows = post_rows()
        assert len(rows) == 1
        assert rows[0]["id"] == new_id
        assert rows[0]["content"] == "hello"


class TestValidationOrder:
    """Edge cases: fixed check order ①→④, first hit reported."""

    def test_count_message_takes_priority_over_format(self):
        imgs = [PNG_IMG] * 9 + [sized("a.gif", 8)]
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("", imgs)
        assert str(excinfo.value) == "图片数量不能超过 9 张"

    def test_format_message_takes_priority_over_size(self):
        imgs = [sized("big.png", posts.MAX_IMAGE_BYTES + 1), sized("a.gif", 8)]
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("", imgs)
        assert str(excinfo.value) == "图片格式仅支持 JPEG/PNG/WebP"

    def test_size_message_takes_priority_over_blank_content(self):
        imgs = [sized("big.png", posts.MAX_IMAGE_BYTES + 1)]
        with pytest.raises(posts.PostError) as excinfo:
            posts.validate_post_submission("", imgs)
        assert str(excinfo.value) == "单张图片不能超过 5MB"


class TestContract:
    """Exported constants and dataclass shape (card §3.2)."""

    def test_constants(self):
        assert posts.MAX_IMAGE_COUNT == 9
        assert posts.MAX_IMAGE_BYTES == 5 * 1024 * 1024
        assert posts.IMAGE_EXTENSIONS == {".jpg", ".jpeg", ".png", ".webp"}

    def test_uploaded_image_is_plain_dataclass(self):
        img = UploadedImage(filename="a.png", data=b"123")
        assert img.filename == "a.png"
        assert img.data == b"123"
