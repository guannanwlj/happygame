# FP-011 Design: Friends-Feed Timeline

Task card: `input/tasks/social-platform/FP-011-friends-feed-timeline.task.md` (sole spec).
Goal: `GET /feed` page aggregating all posts of the current user's friends,
newest first, each entry showing author username and publish time. Friends'
posts only (no own posts, no non-friends), empty state when nothing is
visible, no pagination in this version.

## Merged dependency state

- FP-001 `social_app/db.py` is merged → reuse `db.init_db` / `db.query_all`
  as-is; the §3.1 table slices already exist there verbatim.
- FP-002 (skeleton), FP-003 (auth), FP-008 (friendships), FP-010 (posting)
  are **not** merged → per card §3/§6 build the embedded contracts locally
  and seed data directly; do not wait.

## Approach

- `social_app/feed.py`: `bp = Blueprint("feed", __name__)`, route
  `GET /feed` guarded by `@login_required`. The SQL is the card's §3.1 core
  query contract kept verbatim (one named parameter `:current_user_id`),
  executed through `db.query_all`; rows are passed to the template.
- `social_app/auth.py` (self-built FP-003 contract slice, swapped at
  integration point I-23): login state = Flask session key `user_id`;
  `current_user_id()` returns it or `None`; `login_required(view)`
  redirects anonymous requests to the literal `/login` (no auth blueprint
  exists yet, so no `url_for` target — replaced by the real FP-003 view).
- `social_app/app.py` (self-built minimal Flask shell per §6, replaced by
  FP-002): `create_app()` builds the app, sets `secret_key` from
  `$SECRET_KEY` (dev fallback) so sessions work, idempotently runs
  `db.init_db()`, and registers the feed blueprint.
- `social_app/templates/base.html` + `feed.html`: `feed.html` extends
  `base.html`; a `{% if posts %}` loop renders `username`, `created_at`,
  `content` per entry (Jinja autoescaping keeps D-003 pure-text posts safe),
  an `{% else %}` branch renders the empty state 「暂无好友动态」.

## Key decisions

1. **Contract SQL verbatim**: no extra columns, no `id` in the projection —
   the page needs exactly content/created_at/username; ORDER BY
   `created_at DESC` only, as specified (ISO-8601 strings sort
   chronologically; the schema default guarantees the format).
2. **Named parameter via `dict`**: `db.query_all`'s hint says `tuple` but
   `sqlite3` accepts a mapping for `:name` params; passing
   `{"current_user_id": uid}` keeps the contract SQL unmodified.
3. **Seeds live only in tests** (card §6): friendships inserted as the two
   bidirectional rows (what FP-008's accept flow will produce), posts
   inserted directly with explicit `created_at` values so ordering is
   deterministic.
4. **Login injection in tests**: `client.session_transaction()` sets
   `session["user_id"]` — exactly the §6 session-injection mock; no login
   route is built here.
5. **Exclusions by query, not filtering**: non-friend and own posts never
   enter the result set (the `IN (SELECT friend_id ...)` subquery is the
   visibility boundary), so the template cannot leak them.

## Verification

`python3 -m pytest tests/test_fp011_feed.py -q`, then the full suite.
Scenarios documented in `docs/test-cases/fp011-friends-feed.md`.
