# Design: FP-007 好友请求待处理列表 (Pending Friend Request List)

Task card: `input/tasks/social-platform/FP-007-pending-request-list.task.md`
(nominal sole spec). **Card file not present in this checkout or in any git
history** — the contract below is reconstructed from the in-repo
cross-references that describe FP-007, and follows the house pattern of the
sibling feature tasks:

- FP-002 design decision 4 / INTEGRATION.md I-17: the accept/reject entry
  points (`/friends/requests/<int:req_id>/accept|reject`, variable paths)
  are addressed **by request id from the FP-007 pending list page**
  (list-page buttons); they are not in the top nav.
- FP-002 route table + test S1.2: `/friends/requests` is a fixed nav path.
- FP-006 test C2: `GET /friends/requests` → 405 because "列表属 FP-007，本任务
  只挂 POST" — i.e. **FP-007 owns `GET /friends/requests`**, FP-006 owns the
  POST on the same path.
- FP-006 module docstring: after the skeleton and FP-007 land, sending flips
  to flash + redirect to the pending list (recorded follow-up, not this task).

Trace: UC-003 (friend management). Wave 4. Stack: Python 3.12 + Flask +
SQLite + pytest.

## Goal

Logged-in user opens `GET /friends/requests` and sees the friend requests
**addressed to them** that are still `pending` — one row per request with
the requester's username and the request time, plus per-row accept / reject
entry links addressed by request id (FP-008's targets, per I-17). Read-only:
accepting/rejecting is FP-008, sending is FP-006.

## Merge state of strong dependencies (checked at branch time)

- **FP-001 merged** (commit 9713805): `social_app/db.py` real storage used
  as-is — `friend_requests` (`requester_id`, `addressee_id`, `status` ∈
  {pending, accepted, rejected}, `created_at`) and `users` tables; queried
  through `query_all`.
- **FP-006 NOT merged** → per the fallback instruction (按任务卡 §3 内嵌契约
  自建，勿等待) no waiting: FP-007 does not import FP-006; the only shared
  surface is the URL `/friends/requests`, where the two blueprints coexist
  with disjoint methods (FP-006 `POST`, FP-007 `GET`). Tests seed pending
  `friend_requests` rows directly via `db.execute` (same Mock strategy
  FP-006's own tests used for pre-states).
- **FP-002 NOT merged** → self-build the minimal mounting shell in
  `social_app/__init__.py`: `create_app()` (secret key from
  `SOCIAL_SECRET_KEY`, default `dev-secret`) + `register_blueprints(app)`
  registry, plus a minimal `templates/base.html` with exactly the two
  contract blocks (`title`, `content`) and a flash area (FP-010 precedent).
- **FP-003 NOT merged** → self-build the auth contract slice
  `social_app/auth.py`: `current_user_id()` (`session["user_id"]`, int or
  None) and `login_required` (anonymous → 302
  `/login?next=<request.path>`). Replaced wholesale when FP-003 merges
  (integration point I-22); import sites stay unchanged.

## Approach

- New module `social_app/pending_requests.py` with
  `bp = Blueprint("pending_requests", __name__)` exposing exactly one route:
  `GET /friends/requests`, decorated `@login_required`.
- One SQL query, no ORM:

  ```sql
  SELECT fr.id, fr.created_at, u.username AS requester_username
    FROM friend_requests fr JOIN users u ON u.id = fr.requester_id
   WHERE fr.addressee_id = ? AND fr.status = 'pending'
   ORDER BY fr.created_at DESC, fr.id DESC
  ```

  with `? = current_user_id()`.
- Render `templates/pending_requests.html` (extends `base.html`) with the
  rows; each row shows requester username + `created_at` and two literal-href
  entry links `/friends/requests/<id>/accept` and `/friends/requests/<id>/reject`
  (接受 / 拒绝). Literal hrefs, not `url_for`: FP-008's routes do not exist
  yet and `url_for` would raise `BuildError` — same rationale as FP-002
  design decision 3.
- Empty state: friendly message 暂无待处理请求 (page stays 200).

## Key decisions

1. **Incoming only** (`addressee_id = current_user_id`): "待处理" = requests
   the viewer must act on. Requests the viewer *sent* (pending from their
   side) are somebody else's to process and are excluded — the accept/reject
   entry points are only meaningful for the addressee (FP-008 acts on
   requests addressed to the current user).
2. **`status = 'pending'` filter**: accepted/rejected history never appears
   — the page is an action queue, not a history view (state machine §3.1 of
   the family).
3. **Ordering newest first** (`created_at DESC, id DESC`): follows the
   FP-001 precedent (`idx_posts_created ON posts(created_at DESC)` — lists
   surface newest entries first); `id DESC` is a deterministic tie-break
   because the millisecond timestamp can collide for seeded rows.
4. **Coexistence with FP-006 by disjoint methods on the same path**: two
   blueprints registering `/friends/requests` with non-overlapping `methods`
   dispatch correctly in werkzeug's URL map. No assertion is made that
   `POST /friends/requests` 404s/405s here — that state is temporary until
   FP-006 merges (mirroring FP-002 design decision 8: don't freeze
   transitional states).
5. **Read-only, no side effects**: the view only SELECTs; no flash, no
   redirect. Auto-escaping (`render_template` on `.html`) covers usernames
   containing HTML-special characters.
6. **Stale sessions degrade to empty**: if `session["user_id"]` no longer
   matches a `users` row, the query simply returns no rows → 200 empty
   state (the auth slice guarantees login state exists but not user
   existence; hardening beyond that is FP-003/FP-008 territory).
7. **Test isolation** (Mock strategy, §6 style): fresh temp DB per test via
   `$SOCIAL_DB` + `db.init_db()`; seed users / requests (any status, any
   `created_at`) inserted directly with `db.execute`; login state injected
   via `client.session_transaction()` — no HTTP login flow (FP-003/FP-005
   not merged).

## Files

- `social_app/pending_requests.py` (new) — the feature blueprint.
- `social_app/auth.py` (new) — FP-003 contract slice (stand-in until merge).
- `social_app/__init__.py` (edit) — minimal FP-002 shell contract.
- `social_app/templates/base.html`,
  `social_app/templates/pending_requests.html` (new).
- `tests/test_fp007_pending_requests.py` (new),
  `docs/test-cases/fp007-pending-request-list.md`.

## Verification

`python3 -m pytest tests/test_fp007_pending_requests.py -q`, then the full
suite (`python3 -m pytest`). Scenarios documented in
`docs/test-cases/fp007-pending-request-list.md`.
