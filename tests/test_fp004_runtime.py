"""FP-004 tests: local startup & runtime configuration (`python -m social_app`).

Scenarios documented in docs/test-cases/fp004-runtime-config.md. Subprocess
tests launch the real entrypoint with SOCIAL_DB pointed at a tmp file, so the
repo's default social_platform.db is never touched.
"""

import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing

from packaging.requirements import Requirement

from social_app import __main__ as social_app_main
from social_app import db

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_TABLES = {"users", "friend_requests", "friendships", "posts"}


def _free_port() -> int:
    """Grab an unused TCP port on the loopback interface."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    """One `python -m social_app` subprocess bound to a db file and port."""

    def __init__(self, db_file: str) -> None:
        self.db_file = db_file
        self.proc: subprocess.Popen | None = None
        self.base_url = ""
        self.output = ""

    def start(self) -> "Server":
        port = _free_port()
        self.base_url = f"http://127.0.0.1:{port}"
        env = dict(os.environ, SOCIAL_DB=self.db_file, SOCIAL_PORT=str(port))
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "social_app"],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return self

    def get_status(self, path: str = "/", timeout: float = 20.0) -> int:
        """Poll until the server answers; return its HTTP status code."""
        deadline = time.monotonic() + timeout
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            assert self.proc is not None
            if self.proc.poll() is not None:
                self.output = self.proc.stdout.read() if self.proc.stdout else ""
                raise AssertionError(
                    f"server exited early (rc={self.proc.returncode}):\n{self.output}"
                )
            try:
                with urllib.request.urlopen(self.base_url + path, timeout=1) as resp:
                    return resp.status
            except urllib.error.HTTPError as err:  # any answer proves liveness
                return err.code
            except OSError as err:
                last_error = err
                time.sleep(0.1)
        raise AssertionError(f"server never answered {self.base_url}: {last_error}")

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self.output = self.proc.stdout.read() if self.proc.stdout else ""
        self.proc = None

    def __enter__(self) -> "Server":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()


def tables_in(db_file: str) -> set[str]:
    """Table names inside *exactly* the given file (raw connection)."""
    with closing(sqlite3.connect(db_file)) as conn:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }


def insert_alice(monkeypatch, db_file: str) -> None:
    """Card §6 seed: one users row (alice, h1) via the storage API."""
    monkeypatch.setenv(db.DB_PATH_ENV, db_file)
    db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("alice", "h1"),
    )


def recording_app(calls: list):
    """Fake app recording the kwargs of its run() call."""

    class FakeApp:
        def run(self, **kwargs):
            calls.append(kwargs)

    return FakeApp()


class TestStartupWithSocialDb:
    """Acceptance 1: SOCIAL_DB at a new path — reachable, data in that file."""

    def test_root_responds_and_schema_created_in_social_db_file(self, tmp_path):
        db_file = tmp_path / "nested" / "new.db"
        db_file.parent.mkdir()
        with Server(str(db_file)) as server:
            status = server.get_status("/")
        assert 100 <= status < 500  # any route answering counts (302/404 ok)
        assert db_file.exists()
        assert CORE_TABLES <= tables_in(str(db_file))

    def test_storage_api_write_lands_in_social_db_file(self, tmp_path, monkeypatch):
        db_file = tmp_path / "new.db"
        with Server(str(db_file)) as server:
            assert 100 <= server.get_status("/") < 500
            insert_alice(monkeypatch, str(db_file))
        with closing(sqlite3.connect(str(db_file))) as conn:
            row = conn.execute(
                "SELECT username, password_hash FROM users WHERE username = ?",
                ("alice",),
            ).fetchone()
        assert row is not None
        assert tuple(row) == ("alice", "h1")


class TestRestartPersistence:
    """Acceptance 2: data written before a stop is still there after restart."""

    def test_users_row_survives_stop_and_restart(self, tmp_path, monkeypatch):
        db_file = str(tmp_path / "restart.db")
        server = Server(db_file)
        with server:  # first boot
            assert 100 <= server.get_status("/") < 500
            insert_alice(monkeypatch, db_file)
        with server:  # restart on the same file
            assert 100 <= server.get_status("/") < 500
        with closing(sqlite3.connect(db_file)) as conn:
            row = conn.execute(
                "SELECT username, password_hash FROM users"
            ).fetchone()
        assert row is not None
        assert tuple(row) == ("alice", "h1")


class TestInitIdempotent:
    """§8 item 3: repeated init_db() must not raise."""

    def test_repeated_init_db_keeps_schema(self, tmp_path, monkeypatch):
        db_file = str(tmp_path / "idem.db")
        monkeypatch.setenv(db.DB_PATH_ENV, db_file)
        db.init_db()
        db.init_db()
        with closing(db.get_connection()) as conn:
            db.init_db(conn)
        assert CORE_TABLES <= tables_in(db_file)


class TestRequirementsFile:
    """§8 item 4: requirements.txt exists and parses."""

    def test_requirements_txt_exists(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "requirements.txt"))

    def test_requirements_entries_parse_and_include_flask(self):
        with open(os.path.join(REPO_ROOT, "requirements.txt"), encoding="utf-8") as fh:
            lines = [
                line.strip()
                for line in fh
                if line.strip() and not line.strip().startswith("#")
            ]
        assert lines, "requirements.txt has no requirement lines"
        requirements = [Requirement(line) for line in lines]
        assert "flask" in {req.name.lower() for req in requirements}


class TestEntrypointContract:
    """Unit-level checks on social_app/__main__.py (no subprocess)."""

    def test_load_create_app_returns_working_factory(self):
        app = social_app_main._load_create_app()()
        response = app.test_client().get("/")
        assert response.status_code < 500

    def test_placeholder_app_serves_root(self):
        app = social_app_main._placeholder_create_app()
        assert app.test_client().get("/").status_code == 200

    def test_main_runs_init_db_then_loopback_server(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(db, "init_db", lambda: calls.append("init_db"))
        monkeypatch.setattr(
            social_app_main,
            "_load_create_app",
            lambda: (lambda: recording_app(calls)),
        )
        monkeypatch.setenv("SOCIAL_PORT", "54321")

        social_app_main.main()

        assert calls == [
            "init_db",
            {"host": "127.0.0.1", "port": 54321, "use_reloader": False},
        ]

    def test_main_defaults_to_port_5000(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(db, "init_db", lambda: None)
        monkeypatch.setattr(
            social_app_main,
            "_load_create_app",
            lambda: (lambda: recording_app(calls)),
        )
        monkeypatch.delenv("SOCIAL_PORT", raising=False)

        social_app_main.main()

        assert calls == [{"host": "127.0.0.1", "port": 5000, "use_reloader": False}]
