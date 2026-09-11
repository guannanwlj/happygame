"""SQLite persistence for the social platform (FP-001).

Single storage module for the core tables (users, friend_requests,
friendships, posts, follows). Every later feature task reads and writes
through the generic access API defined here. The database file location is controlled by
the SOCIAL_DB environment variable (read at call time), defaulting to
social_platform.db in the working directory.
"""

import contextlib
import os
import sqlite3
from collections.abc import Iterator

DB_PATH_ENV = "SOCIAL_DB"
DEFAULT_DB_PATH = "social_platform.db"

SCHEMA_SQL = """
-- 用户（D-004 账号凭据＝用户名+密码；密码只存哈希）
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    NOT NULL UNIQUE,
  password_hash TEXT    NOT NULL,
  created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- 好友请求（D-002 好友关系模型＝请求+确认）
CREATE TABLE IF NOT EXISTS friend_requests (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  requester_id INTEGER NOT NULL REFERENCES users(id),
  addressee_id INTEGER NOT NULL REFERENCES users(id),
  status       TEXT    NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending','accepted','rejected')),
  created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
-- 同一方向至多一条待处理请求（防重复，数据库层兜底）
CREATE UNIQUE INDEX IF NOT EXISTS uq_fr_pending
  ON friend_requests(requester_id, addressee_id) WHERE status = 'pending';

-- 好友关系（对称、双向：接受时写 (a,b) 与 (b,a) 两行）
CREATE TABLE IF NOT EXISTS friendships (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  friend_id  INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (user_id, friend_id)
);

-- 帖子（D-003 帖子内容范围＝仅纯文本）
CREATE TABLE IF NOT EXISTS posts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id  INTEGER NOT NULL REFERENCES users(id),
  content    TEXT    NOT NULL,
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);

-- 单向关注（FP-004：A 关注 B 只写 (A,B)，不产生 (B,A)）
CREATE TABLE IF NOT EXISTS follows (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  follower_id INTEGER NOT NULL REFERENCES users(id),
  followee_id INTEGER NOT NULL REFERENCES users(id),
  created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (follower_id, followee_id)
);

-- 点赞（同一用户对同一帖子至多一条，UNIQUE 兜底幂等）
CREATE TABLE IF NOT EXISTS likes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  post_id    INTEGER NOT NULL REFERENCES posts(id),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (user_id, post_id)
);

-- 评论（按帖子读取，时间升序；parent_id 为空＝顶层评论，否则指向顶层父评论）
CREATE TABLE IF NOT EXISTS comments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id    INTEGER NOT NULL REFERENCES posts(id),
  author_id  INTEGER NOT NULL REFERENCES users(id),
  content    TEXT    NOT NULL,
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  parent_id  INTEGER REFERENCES comments(id)
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at);

-- 评论点赞（同一用户对同一评论至多一条，UNIQUE 兜底幂等；独立于帖子 likes 表）
CREATE TABLE IF NOT EXISTS comment_likes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  comment_id INTEGER NOT NULL REFERENCES comments(id),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (user_id, comment_id)
);
"""


def _upgrade_schema(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was first created.

    ``CREATE TABLE IF NOT EXISTS`` leaves an already-created ``comments``
    table untouched, so the FP-002 self-reference column is added explicitly.
    The check makes repeated calls idempotent; existing rows backfill to
    ``NULL`` (top-level comment semantics).
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(comments)")}
    if "parent_id" not in columns:
        conn.execute(
            "ALTER TABLE comments ADD COLUMN parent_id INTEGER REFERENCES comments(id)"
        )


def db_path() -> str:
    """Return the current database file path ($SOCIAL_DB, or the default)."""
    return os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH)


def get_connection() -> sqlite3.Connection:
    """Open a new connection with Row rows and foreign keys enabled.

    The caller owns closing (recommended: ``with closing(get_connection())``).
    """
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Idempotently apply the full schema DDL.

    Uses ``conn`` when given (caller closes it); otherwise opens and closes
    its own connection.
    """
    if conn is None:
        with contextlib.closing(get_connection()) as own:
            own.executescript(SCHEMA_SQL)
            _upgrade_schema(own)
            own.commit()
        return
    conn.executescript(SCHEMA_SQL)
    _upgrade_schema(conn)
    conn.commit()


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Run a read query on a fresh connection and return all rows."""
    with contextlib.closing(get_connection()) as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    """Run a read query and return the first row, or None if no match."""
    with contextlib.closing(get_connection()) as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """Run a single INSERT/UPDATE/DELETE, commit, and return the cursor.

    The cursor's ``lastrowid`` / ``rowcount`` remain usable afterwards.
    """
    with contextlib.closing(get_connection()) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


@contextlib.contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Yield one dedicated connection as an explicit atomic transaction.

    Commits on clean exit, rolls back on any exception.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
