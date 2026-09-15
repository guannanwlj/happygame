"""Post-image metadata persistence (FP-004).

Thin storage layer over the generic API in :mod:`social_app.db`. Each image
of a post is one ``(post_id, storage_name, position)`` row; ``position``
records the submission order (1..n) so the display order (decision D-7)
lives here. Image bytes are written by FP-003 storage — this module only
persists the storage name string. Upload validation (FP-002) and the
POST /posts orchestration (FP-006) are out of scope.
"""

import sqlite3

from social_app import db


def save_post_images(
    post_id: int,
    storage_names: list[str],
    conn: sqlite3.Connection | None = None,
) -> None:
    """Write one row per name, ``position`` = 1..n in list order.

    An empty list writes no rows. Passing ``conn`` executes inside the
    caller's transaction (no commit here — whole-post rollback stays under
    the caller's control, e.g. via :func:`social_app.db.transaction`);
    without ``conn`` a fresh connection is opened and committed.
    """
    if not storage_names:
        return
    rows = [(post_id, name, position) for position, name in enumerate(storage_names, 1)]
    sql = (
        "INSERT INTO post_images (post_id, storage_name, position) VALUES (?, ?, ?)"
    )
    if conn is not None:
        conn.executemany(sql, rows)
        return
    with db.transaction() as own:
        own.executemany(sql, rows)


def list_post_images(post_id: int) -> list[dict]:
    """Return the images of ``post_id`` ordered by ``position`` ASC.

    Each item is ``{"image_id", "post_id", "storage_name", "position"}``.
    A post without images yields ``[]`` (plain-text posts are not an error).
    """
    return [
        {
            "image_id": row["id"],
            "post_id": row["post_id"],
            "storage_name": row["storage_name"],
            "position": row["position"],
        }
        for row in db.query_all(
            "SELECT id, post_id, storage_name, position FROM post_images"
            " WHERE post_id = ? ORDER BY position",
            (post_id,),
        )
    ]
