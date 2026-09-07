# Design: FP-009 我的好友列表 (My Friend List)

Task card: `input/tasks/social-platform/FP-009-friend-list.task.md`
(nominal sole spec). **Card file not present in this checkout or in any git
history** (checked `git log --all --diff-filter=A -- "*FP-009*"` and every
branch tree) — the contract below is reconstructed from the in-repo
cross-references that describe FP-009, following the house pattern of the
sibling feature tasks:

- FP-002 design decision 3 / route table / test `NAV_HREFS`: `/friends` is a
  **fixed nav path** (label 好友列表); the FP-002 index page describes it as
  “好友列表：查看我的好友。” — a page listing *the logged-in user's own*
  friends.
- FP-001 schema comments (merged, `social_app/db.py`): `friendships` is
  symmetric & bidirectional — “接受时写 (a,b) 与 (b,a) 两行”, `UNIQUE
  (user_id, friend_id)`, each row carrying `created_at` (became-friends
  time). FP-009 is the read side of that storage.
- FP-008 (strong dependency, branch task/task-mtqye2a3-c10): accept writes
  the symmetric pair atomically; FP-009 must not import it — the only shared
  surface is the `friendships` table state.
- FP-007 precedent (closest sibling, same read-only shape): pending list is
  `GET /friends/requests`, `@login_required`, newest first, friendly empty
  state, auto-escaped usernames, stale session degrades to empty.

Trace: UC-003 (friend management). Wave 6. Stack: Python 3.12 + Flask +
SQLite + pytest.

## Goal

Logged-in user opens `GET /friends` and sees **their** friends — one row per
friend with the friend's username and the became-friends time, newest first.
Read-only: sending requests is FP-006, acting on them is FP-008, removing a
friend is another task's concern.

## Merge state of dependencies (checked at branch time)

- **FP-001 merged** (commit 9713805): `social_app/db.py` real storage used
  as-is — `query_all` over `friendships` JOIN `users`.
- **FP-008 NOT merged** → per the fallback instruction (按任务卡 §3 内嵌契约
  自建，勿等待) no waiting and no import: tests seed the symmetric
  `friendships` rows directly via `db.execute` (same Mock strategy FP-008's
  own tests used for pre-states; the rows FP-008 will write are exactly the
  symmetric pair the schema documents).
- **FP-002 NOT merged** (weak dependency, 联调面 only) → self-build the
  minimal mounting shell in `social_app/__init__.py`: `create_app()` (secret
  key from `SOCIAL_SECRET_KEY`, default `dev-secret`) +
  `register_blueprints(app)` registry, plus a minimal `templates/base.html`
  with exactly the two contract blocks (`title`, `content`) and a flash area
  (FP-007/FP-010 precedent).
- **FP-003 NOT merged** → self-build the auth contract slice
  `social_app/auth.py`: `current_user_id()` (`session["user_id"]`, int or
  None) and `login_required` (anonymous → 302
  `/login?next=<request.path>`). Replaced wholesale when FP-003 merges
  (integration point I-22); import sites stay unchanged.

## Approach

- New module `social_app/friends.py` with
  `bp = Blueprint("friends", __name__)` exposing exactly one route:
  `GET /friends`, decorated `@login_required`.
- One SQL query, no ORM:

  ```sql
  SELECT f.friend_id, u.username AS friend_username, f.created_at
    FROM friendships f JOIN users u ON u.id = f.friend_id
   WHERE f.user_id = ?
   ORDER BY f.created_at DESC, f.id DESC

  ```

  with `? = current_user_id()`.
- Render `templates/friends.html` (extends `base.html`) with the rows; each
  row shows the friend's username and `created_at` (成为好友时间). No
  per-row action links: un-friending belongs to a later feature and its
  variable paths would need `url_for`/literal hrefs that do not exist yet.
- Empty state: friendly message 暂无好友 (page stays 200).

## Key decisions

1. **Query only the viewer's own direction** (`user_id = current_user_id`):
   symmetry means each friendship yields two rows; reading one direction
   renders each friend exactly once, for every user in the pair (alice sees
   bob, bob sees alice — both from their own row). No `DISTINCT`, no
   OR-union, no dedup logic to get wrong.
2. **`JOIN users` for usernames, never raw ids in the UI**: the friend's
   identity is the username (D-004); `friend_id` stays internal. The join
   also drops orphan rows automatically (FK-enforced, so none can exist).
3. **Ordering newest first** (`created_at DESC, id DESC`): follows the
   FP-001/FP-007 family precedent (lists surface newest entries first);
   `id DESC` is a deterministic tie-break because the millisecond timestamp
   can collide for seeded rows.
4. **GET only**: the page is read-only; `POST /friends` → 405 (automatic —
   no `methods` override). No state change, no flash, no redirect; PRG is
   for actions (FP-008 precedent), not for views.
5. **Auto-escaping covers hostile usernames** (`render_template` on `.html`),
   same as FP-007 decision 5.
6. **Stale sessions degrade to empty**: if `session["user_id"]` no longer
   matches a `users` row, the query simply returns no rows → 200 empty
   state (hardening beyond that is FP-003 territory; FP-007 decision 6).
7. **No self-friendship filter**: `(a, a)` rows cannot arise from the family
   flows (FP-006 blocks self-requests; FP-008 writes the pair only for
   requester ≠ addressee); defending against them here would freeze
   speculative state (cf. FP-002 design decision 8).
8. **Test isolation** (Mock strategy, §6 style): fresh temp DB per test via
   `$SOCIAL_DB` + `db.init_db()`; users / symmetric friendship pairs seeded
   directly with `db.execute` (FP-008 not merged); login state injected via
   `client.session_transaction()` — no HTTP login flow (FP-003/FP-005 not
   merged).

## Files

- `social_app/friends.py` (new) — the feature blueprint.
- `social_app/auth.py` (new) — FP-003 contract slice (stand-in until merge).
- `social_app/__init__.py` (edit) — minimal FP-002 shell contract.
- `social_app/templates/base.html`, `social_app/templates/friends.html`
  (new).
- `tests/test_fp009_friend_list.py` (new),
  `docs/test-cases/fp009-friend-list.md`.

## Verification

`python3 -m pytest tests/test_fp009_friend_list.py -q`, then the full suite
(`python3 -m pytest`). Scenarios documented in
`docs/test-cases/fp009-friend-list.md`.
