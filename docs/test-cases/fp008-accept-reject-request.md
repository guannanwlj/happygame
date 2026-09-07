# Test Cases: FP-008 接受/拒绝好友请求 (Accept/Reject Friend Request)

Source: task card FP-008 §7 acceptance + §8 suggested tests (card file absent
— scenarios reconstructed from the in-repo contract references, see
`docs/designs/fp008-accept-reject-request.md`).
File: `tests/test_fp008_friend_request_actions.py`.
Command: `python3 -m pytest tests/test_fp008_friend_request_actions.py -q`.

## Fixture / mock isolation (task-card §6 style)

- Fresh temp SQLite DB per test (`SOCIAL_DB` → tmp file) + `db.init_db()`
  (FP-001 merged, real storage used).
- Seed users / `friend_requests` rows (any status, explicit old
  `created_at`/`updated_at` so timestamp refresh is deterministic) /
  `friendships` rows inserted directly via `db.execute` (FP-006 not merged
  → direct seeding, same Mock strategy FP-006's own tests used).
- Login state injected via `client.session_transaction()["user_id"]`
  (FP-003 not merged → session injection, integration point I-22).
- App built by the minimal self-built `create_app()` shell (FP-002 not
  merged → self-built mounting shell). No HTTP server.
- Redirects asserted via the `Location` header only, never followed
  (the redirect target page belongs to FP-007, not mounted here).

## Scenarios

### A. Acceptance — main paths (GWT)

| # | Given | When | Then |
|---|-------|------|------|
| A1 | logged-in `alice`; `bob→alice` pending (old timestamps) | GET `/friends/requests/<id>/accept` | 303; `Location: /friends/requests`; flash `好友请求已接受`; row → `accepted` with refreshed `updated_at`; friendships contain both `(alice,bob)` and `(bob,alice)` |
| A2 | logged-in `alice`; `bob→alice` pending | GET `/friends/requests/<id>/reject` | 303; `Location: /friends/requests`; flash `好友请求已拒绝`; row → `rejected` with refreshed `updated_at`; **zero** friendship rows |
| A3 | same as A1 | POST `.../accept` | identical outcome to A1 (GET/POST twins) |
| A4 | same as A2 | POST `.../reject` | identical outcome to A2 |

### B. Authorization / addressing (only the addressee of a pending row)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | requester tries to accept their **own outgoing** pending request | 404; row still `pending`; no friendship rows |
| B2 | uninvolved third party (`carol`) tries accept and reject on alice's incoming request | 404 both; row still `pending`; no friendship rows |
| B3 | anonymous (no `user_id` in session) hits accept | 302 to `/login?next=/friends/requests/<id>/accept`; row untouched |
| B4 | anonymous hits reject | 302 to `/login?next=/friends/requests/<id>/reject`; row untouched |
| B5 | stale session (`user_id` with no `users` row) hits accept | 404; row untouched |

### C. State machine — processed / nonexistent requests

| # | Scenario | Expected |
|---|----------|----------|
| C1 | accept the same request twice (second GET after success) | second → 404; still exactly 2 friendship rows; status stays `accepted` |
| C2 | accept a request that is already `rejected` | 404; stays `rejected`; no friendship rows |
| C3 | reject a request that is already `accepted` | 404; stays `accepted`; friendship pair intact |
| C4 | accept / reject a nonexistent request id | 404 both; zero rows anywhere |
| C5 | non-integer request id (`/friends/requests/abc/accept`, `.../abc/reject`) | 404 (int converter; no route match) |

### D. Side-effect isolation / invariants

| # | Scenario | Expected |
|---|----------|----------|
| D1 | two pending requests to alice (`bob→alice`, `carol→alice`); accept bob's | carol's row still `pending`; only the bob–alice friendship pair exists |
| D2 | anomaly: alice–bob already friends in one direction while `bob→alice` pending; accept | 303 (no 500); both directions now present (end-state idempotent, `INSERT OR IGNORE`) |
| D3 | reject while an unrelated friendship pair exists (alice–carol friends, `carol→alice`… requester differs) — reject `bob→alice` | alice–carol friendship rows unchanged; no bob–alice rows |
| D4 | accept then check the requester's other pending outgoing request (to dave) | that row still `pending`; no bob–dave rows (only the acted pair changes) |

### E. Shell / mounting contract (FP-002 slice)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `create_app().url_map` | contains both variable rules `/friends/requests/<int:req_id>/accept` and `.../reject`, each allowing GET and POST |
| E2 | `SOCIAL_SECRET_KEY` env override | `create_app().secret_key` follows the env value (shell contract) |
| E3 | unallowed method (PUT) on an accept URL | 405 |

## Non-assertions (transitional states, cf. FP-002 design decision 8)

- No assertion that `GET /friends/requests` (redirect target) renders —
  FP-007's page, not mounted on this branch.
- No assertion about `POST /friends/requests` — FP-006's route.
- No assertion that the flashed message renders in HTML — that requires
  FP-007's `base.html`; here the flashed messages are asserted in the
  session (the transport the flash area reads after merge).
