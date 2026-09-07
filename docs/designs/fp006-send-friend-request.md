# FP-006 Design: Send Friend Request

Task card: `input/tasks/social-platform/FP-006-send-friend-request.task.md`
(sole spec). Goal: logged-in user targets another user by username; the system
validates (target exists → not self → not already friends → no pending request
in **either** direction) and, when everything passes, stores a `pending`
friend request.

## Approach

- New module `social_app/friends_request.py` with
  `bp = Blueprint("friend_request", __name__)` and the single route
  `POST /friends/requests` (form field `username`), decorated with
  `@login_required` — exactly the mounting contract of card §3.2.
- Validation order and semantics come verbatim from card §4; each failure
  returns its specific message and writes nothing:
  1. target username exists (exact match on `users.username`; the form value
     is stripped, missing/blank ⇒ no such user),
  2. target is not the requester themself,
  3. the pair is not friends yet (`friendships` probed in both directions,
     although FP-001 stores both rows),
  4. no `pending` request exists A↔B in either direction (equivalent
     implementation of "相互无未处理请求" per §4).
- All checks pass → `INSERT` one row
  (`requester_id = current_user_id()`, `addressee_id = target`,
  `status = 'pending'` via column default) through the already-merged
  FP-001 storage API (`query_one` / `execute` from `social_app/db.py`).
- `rejected` history never blocks: a fresh resend inserts a **new** `pending`
  row and leaves the old `rejected` row untouched (state machine §3.1).

## Dependency slices (strong deps not merged — self-built per §3/§6)

- **FP-001** (merged): real `social_app/db.py` used as-is — integration
  point I-09 already satisfied.
- **FP-003** (not merged): new `social_app/auth.py` implementing the card
  §3.2 contract slice FP-006 needs — `current_user_id() -> int | None`
  (`session.get('user_id')`) and `login_required(view)` (unauthenticated →
  302 `/login?next=<request.path>`). No password hashing/session login
  helpers here: out of FP-006 scope. When FP-003 merges, this slice is
  replaced wholesale by the full module (integration point I-11); the
  import sites in `friends_request.py` stay unchanged.
- **FP-002** (not merged): no app factory touched. Tests mount the blueprint
  on a minimal self-built Flask shell (`Flask(__name__)` + `secret_key` +
  `app.register_blueprint(bp)`) per card §6. When FP-002 merges, the only
  change is appending `app.register_blueprint(friends_request.bp)` to
  `register_blueprints(app)` (integration point I-10).

## Key decisions

1. **Plain-text responses, no templates.** FP-002's `base.html` does not
   exist yet, and redirect targets (pending list is FP-007, index is FP-002)
   do not exist either. The view therefore returns the message string as the
   response body: 200 on success, 400 on every validation failure. When the
   skeleton and FP-007 land, this switches to flash + redirect (recorded as
   part of I-10/I-14 follow-up; assertions in tests target status + message
   text, so the swap stays cheap).
2. **Chinese messages locked to the card wording** so acceptance wording and
   test assertions map 1:1: `用户不存在` / `不能加自己` / `已是好友` /
   `已有待处理请求` / success `好友请求已发送`.
3. **Either-direction pending check** (not just same-direction): card §4
   explicitly makes the reverse pending (bob→alice) block a new alice→bob
   request. Seed from §6 exercises this.
4. **Duplicate-pending semantics = reject, never reuse.** The partial unique
   index `uq_fr_pending` (FP-001) is the database-level backstop: the INSERT
   wraps in `try/except sqlite3.IntegrityError` and maps a race-induced hit
   to the same `已有待处理请求` failure — no second `pending` row can exist.
5. **Tests inject login state directly** via `session_transaction()`
   (`session['user_id'] = <id>`) instead of any login flow, and seeds users
   `alice`/`bob`/`carol` straight into SQLite (FP-004 is a weak dependency,
   card §6) — one seed helper per §6 datum (friendship pair, rejected
   request, reverse pending) composed per test, because the acceptance
   scenarios need mutually exclusive pre-states.

## Verification

`python3 -m pytest tests/test_fp006_friend_request.py -q`, then the full
suite. Scenarios documented in `docs/test-cases/fp006-send-friend-request.md`.
