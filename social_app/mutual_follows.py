"""Mutual-follow (相互关注) check primitive (FP-001).

Real-time boolean decision over the one-directional ``follows`` table: two
users are mutual followers iff both directions (A→B and B→A) exist as rows.
Every call derives the answer from the current ``follows`` data — no
snapshot or cache table is written, so the semantics automatically follow
relationship changes (follow added / row deleted). The legacy
request+confirm friend tables (``friend_requests`` / ``friendships``) are
never read or written here.
"""

from social_app.follows import is_following


def is_mutual_follow(a_id: int, b_id: int) -> bool:
    """Return ``True`` iff ``a_id`` and ``b_id`` follow each other.

    Equivalent to ``is_following(a_id, b_id) and is_following(b_id, a_id)``;
    computed fresh on each call (no snapshot). The self-pair
    ``a_id == b_id`` is undefined upstream; no behavior is promised for it.
    """
    return is_following(a_id, b_id) and is_following(b_id, a_id)
