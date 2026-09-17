"""Mutual friend circle computation (FP-002).

Real-time derivation of the mutual friend circle: the set of users who are
mutual follows of **both** ``reader_id`` and ``author_id``. There is no
snapshot table — every call reads the current ``follows`` data, so follow or
unfollow events are reflected by the next call.

Whether the reader and the author are mutual follows is deliberately NOT
part of this computation: deciding if the friend-post filter applies at all
is the caller's responsibility (FP-003 feed dispatch). The legacy
``friendships`` table (request+confirm model) is unrelated and never read.
"""

from social_app import db

# A user m belongs to the circle iff four follows rows exist simultaneously:
# m→R, R→m, m→P, P→m. m ranges over followers of R; UNIQUE(follower_id,
# followee_id) guarantees each m yields at most one row, so no DISTINCT is
# needed.
_MUTUAL_FRIENDS_SQL = """
SELECT m.follower_id AS friend_id
FROM follows m
WHERE m.followee_id = ?
  AND EXISTS (SELECT 1 FROM follows
              WHERE follower_id = ? AND followee_id = m.follower_id)
  AND EXISTS (SELECT 1 FROM follows
              WHERE follower_id = m.follower_id AND followee_id = ?)
  AND EXISTS (SELECT 1 FROM follows
              WHERE follower_id = ? AND followee_id = m.follower_id)
"""


def mutual_friend_ids(reader_id: int, author_id: int) -> set[int]:
    """Return the ids of users mutual with both reader and author.

    Real-time computation over the ``follows`` table (no snapshot, no cache);
    pure read — nothing is written. Does not judge whether the reader and the
    author are mutual follows; enabling that filter is up to the caller.
    """
    rows = db.query_all(
        _MUTUAL_FRIENDS_SQL, (reader_id, reader_id, author_id, author_id)
    )
    return {row["friend_id"] for row in rows}
