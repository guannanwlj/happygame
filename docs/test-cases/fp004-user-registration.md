# FP-004 Test Scenarios — 用户注册（User Registration）

Module under test: `social_app/register.py` (blueprint `bp`, `GET/POST
/register`). Spec: reconstructed FP-004 contract — see
`docs/designs/fp004-user-registration.md` for the card-absence situation and
the flagged assumptions. Dependencies: real FP-001 `db` module (fresh
`SOCIAL_DB` tmp file per test); self-built FP-003 `auth` stand-in (hash
contract); test-local minimal Flask shell in place of FP-002 `create_app()`
(FP-003 card §6 mock strategy, mirrored).

Validation rules under test (design assumptions): username `[A-Za-z0-9_]`
3–30 chars after `strip()`; password verbatim 6–128 chars; duplicate username
rejected; errors re-render the form (HTTP 200) with the message and the
submitted username preserved; success 302 → `/login` + flash.

## A. Registration form (`GET /register`)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Anonymous GET `/register` | 200; `text/html`; page contains the 注册 heading |
| A2 | Form markup | `<form method="post" action="/register">`; inputs named `username` and `password`; a submit control |
| A3 | Fresh form shows no error | No `class="error"` element rendered |
| A4 | GET performs no writes | `users` table stays empty after the request |

## B. Happy path (`POST /register` valid input)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | POST `alice` / `alice-pass-123` | 302; `Location` ends with `/login` |
| B2 | Row persisted correctly | Exactly one row, `username='alice'`, `created_at` populated |
| B3 | Password never stored in plaintext (D-004) | `password_hash` matches `pbkdf2:sha256$<int>$<hex>$<hex>`, differs from the plaintext; plaintext absent from the whole row |
| B4 | Hash is verifiable through the auth contract | `verify_password(pw, stored)` True; wrong password False |
| B5 | Success flash queued | Session carries the success message after the redirect |
| B6 | Boundary username `a`×30, password `abc123` (6) | 302; row created (rules are inclusive bounds) |
| B7 | Same password, two users → different hashes | Per-user random salt (FP-003 contract) |
| B8 | Username with digits/underscore (`user_01`) | 302; row created |

## C. Duplicate username

| # | Scenario | Expected |
|---|----------|----------|
| C1 | POST a username that already exists | 200; `USERNAME_TAKEN` message shown; row count unchanged |
| C2 | Race backstop: pre-check bypassed (`username_exists` → False), UNIQUE still hits | 200 with the taken message (no 500); row count unchanged |
| C3 | Duplicate error page preserves the entered username | Echoed (escaped) in the form |

## D. Username validation errors

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `username` field missing entirely | 200; `USERNAME_REQUIRED`; no row |
| D2 | Empty string / whitespace-only | 200; `USERNAME_REQUIRED`; no row |
| D3 | Too short (`ab`) | 200; `USERNAME_INVALID`; no row |
| D4 | Too long (`a`×31) | 200; `USERNAME_INVALID`; no row |
| D5 | Bad charset: embedded space, `-`, CJK | 200; `USERNAME_INVALID`; no row |
| D6 | Username is validated before password | Empty username + empty password → the username error is reported |

## E. Password validation errors

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `password` field missing entirely | 200; `PASSWORD_INVALID`; no row |
| E2 | Empty password | 200; `PASSWORD_INVALID`; no row |
| E3 | Too short (`abc12`, 5 chars) | 200; `PASSWORD_INVALID`; no row |
| E4 | Too long (`x`×129) | 200; `PASSWORD_INVALID`; no row |
| E5 | Valid username + invalid password → username not consumed | No row; entered username still echoed |

## F. Output escaping (XSS defense)

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Username `<script>alert(1)</script>` (fails charset rule) | 200; error page contains `&lt;script&gt;`; raw `<script>alert` never appears |

## G. Mounting contract & isolation

| # | Scenario | Expected |
|---|------|----------|
| G1 | `register.bp` is a Blueprint named `register` | Mountable on any Flask app; `GET /register` served after `register_blueprint` |
| G2 | Default DB untouched | No `social_platform.db` appears in the working directory |

Test file: `tests/test_fp004_register.py`.
