# FP-019 Test Scenarios — Interaction Authorization Guard

Module under test: `social_app/interaction_service.py`
(`InteractionError`, `authorize_interaction`) against the existing `posts` and
`follows` tables (spec: task card FP-019 §3.2/§4/§7/§8). Every test uses a fresh
temporary DB file via the `SOCIAL_DB` env var, calls `db.init_db()`, then seeds
users/posts/follows — no shared state, no repo pollution.

Seed helpers used throughout: `insert_user(username)`, `insert_post(author)`,
`follow(follower, followee)`, and `table_counts()` (row count of every table in
`sqlite_master`).

## A. Acceptance 1 — author is authorized

| # | Scenario | Expected |
|---|----------|----------|
| A1 | A authors P; `authorize_interaction(A, P)` | Returns `None`, no exception |
| A2 | A authors P after other unrelated rows | Still returns `None` (no side effects) |

## B. Acceptance 2 — follower is authorized

| # | Scenario | Expected |
|---|----------|----------|
| B1 | A follows B; B authors P; `authorize_interaction(A, P)` | Returns `None` |
| B2 | A follows B (stored as one row); B authors P | Follow query sees `(A,B)` and allows |

## C. Acceptance 3 — non-follower, non-author denied without writes

| # | Scenario | Expected |
|---|----------|----------|
| C1 | A does not follow C; C authors P; `authorize_interaction(A, C_post)` | Raises `InteractionError` |
| C2 | Error text of C1 | Readable Chinese `"无权互动该帖子"` |
| C3 | Every table's row count before vs. after C1 | Unchanged (`follows`/`posts`/`likes`, plus `comments` if present) |
| C4 | Directionality: A follows B; A authors P; `authorize_interaction(B, P)` | Denied — B following is not implied by A following B |
| C5 | A follows C but C authors no post; unrelated P by D; `authorize_interaction(A, P)` | Denied |

## D. Acceptance 4 — missing post denied without writes

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `authorize_interaction(A, 9999)` with A seeded | Raises `InteractionError` |
| D2 | Error text of D1 | Readable Chinese `"帖子不存在"` |
| D3 | Row counts before vs. after D1 | Unchanged |
| D4 | Post deleted after id was known | Raises `InteractionError("帖子不存在")` |

## E. Anonymous actor

| # | Scenario | Expected |
|---|----------|----------|
| E1 | P exists; `authorize_interaction(None, P)` | Raises `InteractionError("未登录")` |
| E2 | Row counts before vs. after E1 | Unchanged |
| E3 | `actor_id=None` and post missing | `"帖子不存在"` wins (card §4 step order) |

## F. Contract / hook points

| # | Scenario | Expected |
|---|----------|----------|
| F1 | `issubclass(InteractionError, Exception)` | `True` |
| F2 | `authorize_interaction` return on allow | Exactly `None` |
| F3 | Monkeypatch `interaction_service.is_following` → `True` for a non-follower | Call returns `None`, proving the module-level dependency hook |
| F4 | Module has no write path: source contains no `db.execute`/`INSERT`/`UPDATE`/`DELETE` | `True` |

Skeleton/test file: `tests/test_fp019_interaction_guard.py`.
