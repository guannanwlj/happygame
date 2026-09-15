"""FP-003 tests: 图片文件存储（image_storage）.

Scenarios documented in docs/test-cases/fp003-image-storage.md. Every test
uses a fresh temporary directory through the SOCIAL_IMAGE_DIR environment
variable (read at call time), so the repo never gains an uploads/ folder.
"""

import os

import pytest

from social_app import image_storage
from social_app.image_storage import ImageStorageError

IMAGE_BYTES = b"\x89PNG\r\n\x1a\nfake-image-bytes"


@pytest.fixture(autouse=True)
def temp_image_dir(tmp_path, monkeypatch):
    """Point SOCIAL_IMAGE_DIR at a fresh temp directory per test."""
    directory = tmp_path / "imgs"
    monkeypatch.setenv(image_storage.IMAGE_DIR_ENV, str(directory))
    return directory


def dir_entries(directory) -> set[str]:
    return {entry.name for entry in os.scandir(directory)}


class TestSaveImage:
    """Acceptance 1: save bytes, extension lower-cased, exact content."""

    def test_save_writes_file_with_normalized_extension(self, temp_image_dir):
        name = image_storage.save_image(IMAGE_BYTES, "photo.PNG")
        assert "/" not in name and "\\" not in name
        assert name.endswith(".png")
        assert (temp_image_dir / name).read_bytes() == IMAGE_BYTES

    @pytest.mark.parametrize("original", ["pic.PNG", "pic.JpG", "pic.jpeg"])
    def test_extension_lowercased(self, original):
        name = image_storage.save_image(IMAGE_BYTES, original)
        expected = "." + original.rsplit(".", 1)[1].lower()
        assert name.endswith(expected)

    def test_filename_without_extension_yields_bare_token(self, temp_image_dir):
        name = image_storage.save_image(IMAGE_BYTES, "photo")
        assert "." not in name
        assert (temp_image_dir / name).read_bytes() == IMAGE_BYTES


class TestNoOverwrite:
    """Acceptance 2: repeated uploads never clobber an existing file."""

    def test_token_collision_regenerates_and_keeps_existing_file(
        self, temp_image_dir, monkeypatch
    ):
        temp_image_dir.mkdir()
        existing = temp_image_dir / "aaaa.png"
        existing.write_bytes(b"old-bytes")
        tokens = iter(["aaaa", "bbbb"])
        monkeypatch.setattr(
            image_storage.secrets, "token_urlsafe", lambda _: next(tokens)
        )
        name = image_storage.save_image(IMAGE_BYTES, "photo.png")
        assert name == "bbbb.png"
        assert existing.read_bytes() == b"old-bytes"
        assert (temp_image_dir / name).read_bytes() == IMAGE_BYTES

    def test_same_original_filename_twice_gives_distinct_names(
        self, temp_image_dir
    ):
        first = image_storage.save_image(IMAGE_BYTES, "photo.png")
        second = image_storage.save_image(IMAGE_BYTES, "photo.png")
        assert first != second
        assert (temp_image_dir / first).read_bytes() == IMAGE_BYTES
        assert (temp_image_dir / second).read_bytes() == IMAGE_BYTES


class TestFailureSemantics:
    """Acceptance 3: ImageStorageError + zero residue in the directory."""

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="root ignores directory permission bits",
    )
    def test_unwritable_directory_raises_without_residue(self, temp_image_dir):
        temp_image_dir.mkdir()
        os.chmod(temp_image_dir, 0o500)
        try:
            with pytest.raises(ImageStorageError):
                image_storage.save_image(IMAGE_BYTES, "photo.png")
            assert dir_entries(temp_image_dir) == set()
        finally:
            os.chmod(temp_image_dir, 0o700)

    def _raise_oserror(self, *_args, **_kwargs):
        raise OSError("injected failure")

    @pytest.mark.parametrize("patched", ["write", "replace"])
    def test_write_failure_cleanup(self, temp_image_dir, monkeypatch, patched):
        temp_image_dir.mkdir()
        monkeypatch.setattr(os, patched, self._raise_oserror)
        with pytest.raises(ImageStorageError) as excinfo:
            image_storage.save_image(IMAGE_BYTES, "photo.png")
        assert str(excinfo.value)
        assert dir_entries(temp_image_dir) == set()

    def test_message_is_readable_chinese(self, temp_image_dir, monkeypatch):
        temp_image_dir.mkdir()
        monkeypatch.setattr(os, "write", self._raise_oserror)
        with pytest.raises(ImageStorageError) as excinfo:
            image_storage.save_image(IMAGE_BYTES, "photo.png")
        message = str(excinfo.value)
        assert message and any("\u4e00" <= ch <= "\u9fff" for ch in message)


class TestDefaultDirectory:
    """Acceptance 4: SOCIAL_IMAGE_DIR unset → ./uploads under cwd."""

    def test_falls_back_to_uploads_relative_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.delenv(image_storage.IMAGE_DIR_ENV, raising=False)
        monkeypatch.chdir(tmp_path)
        assert image_storage.image_dir() == "uploads"
        name = image_storage.save_image(IMAGE_BYTES, "photo.PNG")
        assert (tmp_path / "uploads" / name).read_bytes() == IMAGE_BYTES


class TestDirectoryCreation:
    """Acceptance 5: missing directory is auto-created."""

    def test_missing_directory_created_on_demand(self, temp_image_dir):
        assert not temp_image_dir.exists()
        name = image_storage.save_image(IMAGE_BYTES, "photo.png")
        assert (temp_image_dir / name).read_bytes() == IMAGE_BYTES


class TestContractShape:
    """Extra: randomness and call-time env resolution."""

    def test_image_dir_reads_env_at_call_time(self, monkeypatch, tmp_path):
        first = tmp_path / "one"
        second = tmp_path / "two"
        monkeypatch.setenv(image_storage.IMAGE_DIR_ENV, str(first))
        assert image_storage.image_dir() == str(first)
        monkeypatch.setenv(image_storage.IMAGE_DIR_ENV, str(second))
        assert image_storage.image_dir() == str(second)

    def test_constants_exposed(self):
        assert image_storage.IMAGE_DIR_ENV == "SOCIAL_IMAGE_DIR"
        assert image_storage.DEFAULT_IMAGE_DIR == "uploads"
