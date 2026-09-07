# Design: FP-008 接受/拒绝好友请求 (Accept/Reject Friend Request)

Task card: `input/tasks/social-platform/FP-008-accept-reject-request.task.md`
(nominal sole spec). **Card file not present in this checkout or in any git
history** — the contract below is reconstructed from the in-repo
cross-references that describe FP-008, following the house pattern of the
sibling feature tasks:

- FP-002 design decision 4 / route table: the variable paths
  `/friends/requests/<int:req_id>/accept|reject` are FP-008's routes; they
  are addressed **by request id from the FP-007 pending list page**
  (INTEGRATION.md I-17: 列表页按钮), never from the top nav.
- FP-007 (branch task/task-mtqye2a3-c09) renders those entry points as
  literal-href anchors `接受` / `拒绝` addressed by request id — so the
  action routes must be **GET-reachable**.
- FP-001 (merged) schema comments: `friend_requests.status` ∈
  {pending, accepted, rejected}; "好友关系（对称、双向：接受时写 (a,b) 与
  (b,a) 两行）" — accepting flips the request to `accepted` **and** writes
  both symmetric `friendships` rows; FP-001's `transaction()` exists exactly
  for such multi-statement atomic writes.
- FP-006 design: only `pending` rows are actionable; `accepted`/`rejected`
  history never mutates or blocks later sends (family state machine §3.1).
- FP-010 pattern: after a state-changing action, flash a Chinese message and
  redirect 303 (PRG).

Trace: UC-003 (friend management). Wave 5. Stack: Python 3.12 + Flask +
SQLite + pytest.

## Goal

The addressee of a `pending` friend request acts on it from the FP-007 list
page: **accept** (request → `accepted`, both symmetric friendship rows
written atomically) or **reject** (request → `rejected`, no friendship
rows). After either action the viewer is flashed a confirmation and sent
back to the pending list.

## Merge state of strong dependencies (checked at branch time)

- **FP-001 merged** (commit 9713805): `social_app/db.py` real storage used
  as-is — `query_one` / `execute` / `transaction` over `friend_requests`
  and `friendships`.
- **FP-006 NOT merged** → no import; tests seed `friend_requests` rows
  directly via `db.execute` (same Mock strategy FP-006's own tests used).
- **FP-007 NOT merged** → no import; the redirect target
  `/friends/requests` is asserted as the `Location` header only (never
  followed — rendering that page is FP-007's job).
- **FP-003 NOT merged** → self-build the auth contract slice
  `social_app/auth.py`: `current_user_id()` (`session["user_id"]`, int or
  None) and `login_required` (anonymous → 302
  `/login?next=<request.path>`), hardened variant from the FP-010 wave
  (non-int session values degrade to anonymous). Replaced wholesale when
  FP-003 merges (integration point I-22); import sites stay unchanged.
- **FP-002 NOT merged** → self-build the minimal mounting shell in
  `social_app/__init__.py`: `create_app()` (secret key from
  `SOCIAL_SECRET_KEY`, default `dev-secret`) + `register_blueprints(app)`
  registry. **No template shipped**: the action views never render (PRG);
  the flashed message lands on FP-007's page, which owns `base.html`.

## Approach

- New module `social_app/friend_request_actions.py` with
  `bp = Blueprint("friend_request_actions", __name__)` exposing exactly two
  routes, both `methods=("GET", "POST")` and `@login_required`:

  ```
  /friends/requests/<int:req_id>/accept
  /friends/requests/<int:req_id>/reject
  ```

  GET must work because FP-007's list renders plain anchor hrefs (I-17);
  POST is allowed too so the entry points can later become forms without a
  route change.

- **Accept** — one `db.transaction()`, statement-guarded (no read-then-write
  TOCTOU):

  1. `UPDATE friend_requests SET status='accepted', updated_at=<now>
     WHERE id=? AND addressee_id=? AND status='pending'`;
     `rowcount != 1` → `abort(404)` (raises inside the transaction →
     rollback, zero state change).
  2. `SELECT requester_id` of that row (same transaction, row already
     matched).
  3. `INSERT OR IGNORE INTO friendships` the symmetric pair
     `(addressee, requester)` and `(requester, addressee)`.

  Then `flash("好友请求已接受")` + `redirect("/friends/requests", 303)`.

- **Reject** — single guarded `UPDATE` via `db.execute` (atomic by itself):
  `pending → rejected` + refreshed `updated_at`, same WHERE guard,
  `rowcount != 1` → 404. No friendship writes. Then
  `flash("好友请求已拒绝")` + `redirect("/friends/requests", 303)`.

- `updated_at` is refreshed SQL-side with the schema's own expression
  `strftime('%Y-%m-%dT%H:%M:%fZ','now')`, keeping each mutation one
  statement inside the transaction.

## Key decisions

1. **Only the addressee, only `pending`** — the WHERE guard
   (`id AND addressee_id = current_user_id() AND status='pending'`) is the
   whole authorization + state-machine check; `rowcount` is its single
   return signal. Requester, third parties, stale sessions, and already
   processed (accepted/rejected) requests all match zero rows.
2. **404, not 403, for every non-actionable case.** A foreign request id
   must not leak whether it exists or who owns it (the addressee's queue is
   the only entry surface, I-17). A uniform 404 with zero state change
   keeps double-accept and replay semantics trivial: once processed, the
   row is simply no longer pending.
3. **Atomic accept via `transaction()`** — the guarded UPDATE and both
   friendship INSERTs commit or roll back together (FP-001's documented
   purpose for `transaction()`), so no partial state ("accepted without
   friendships") can be observed. The `abort(404)` path rolls back through
   the context manager's exception handling.
4. **`INSERT OR IGNORE` for the friendship pair** — `friendships` has
   `UNIQUE (user_id, friend_id)`; a pre-existing row (data anomaly: pair
   befriended through another path while the request sat pending) would
   otherwise abort the accept with an IntegrityError/500. OR IGNORE makes
   accept **end-state idempotent**: after it returns, both directions
   exist — never fewer, never duplicates.
5. **PRG back to the pending list** (FP-010 precedent): flash + 303 to
   `/friends/requests` (literal path, not `url_for` — FP-007's blueprint is
   not mounted here; same rationale as FP-002 design decision 3). The
   flashed message is carried in the session and rendered by FP-007's
   `base.html` flash area after merge; on this branch nothing renders it,
   so tests assert the session's flashed messages directly.
6. **GET mutates state** — deliberately not REST-pure, because I-17 fixed
   the entry contract as literal-href buttons on the list page; blocking
   GET would make FP-007's shipped markup dead. POST is accepted as a
   forward-compatible twin (same handler, no method branching).
7. **No template of its own** — actions always redirect (303), so nothing
   renders; `base.html` remains FP-007/FP-002 territory and is not
   duplicated here.
8. **Test isolation** (Mock strategy, §6 style): fresh temp DB per test via
   `$SOCIAL_DB` + `db.init_db()`; users / requests / friendships seeded
   directly with `db.execute` (FP-006 not merged); login state injected via
   `client.session_transaction()` (FP-003 not merged); app from the
   self-built `create_app()` shell (FP-002 not merged). Redirects are
   asserted by `Location` header, never followed (FP-007's page absent).

## Files

- `social_app/friend_request_actions.py` (new) — the two action routes.
- `social_app/auth.py` (new) — FP-003 contract slice (stand-in until merge).
- `social_app/__init__.py` (edit) — minimal FP-002 shell contract
  (`create_app` / `register_blueprints`).
- `tests/test_fp008_friend_request_actions.py` (new),
  `docs/test-cases/fp008-accept-reject-request.md`.

## Verification

`python3 -m pytest tests/test_fp008_friend_request_actions.py -q`, then the
full suite (`python3 -m pytest`). Scenarios documented in
`docs/test-cases/fp008-accept-reject-request.md`.
