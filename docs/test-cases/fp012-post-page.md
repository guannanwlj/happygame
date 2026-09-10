# FP-012 Test Scenarios — Post Page

Module under test: `social_app/views_post.py` (spec: task card
FP-012 §3.3/§4/§7/§8). Requests are dispatched directly through
`SocialApp.dispatch(Request(...))`, so no network is involved. FP-013
(`social_app.posts.create_post` / `PostError`) is isolated with a stub via
the card §6 monkeypatch strategy; FP-003 login state is either stubbed
(`views_post.require_login` / `views_post.current_user_id`) or exercised with
a real session token.

## A. Render the form (logged in)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `GET /posts/new`, logged in | 200, HTML content type, page contains a `<textarea name="content">` |
| A2 | Form posts back to `/posts` | Body contains `action="/posts"` and `method="post"` |
| A3 | Anonymous `GET /posts/new` | `require_login` response returned unchanged: 303, `Location: /login`; form not rendered |

## B. Submit non-empty text

| # | Scenario | Expected |
|---|----------|----------|
| B1 | `POST /posts`, body `b"content=hello"`, logged in | 303 redirect, `Location: /` |
| B2 | Same request | `create_post` called exactly once with `(author_id, "hello")` |
| B3 | `+`/percent-encoded body (`content=hello+world`) | Decoded to `hello world` before `create_post` |
| B4 | Real FP-003 session cookie for user 7 | `create_post` receives `7` as `author_id` |

## C. Submit empty / whitespace content

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Body `b"content=%20%20"` (all whitespace) | 200 (no redirect), body contains `不能为空` |
| C2 | Body `b"content="` (empty string) | 200, body contains `不能为空` |
| C3 | Body with no `content` field | 200, `create_post` called with `""`, message `不能为空` |
| C4 | Error page preserves the form | `<textarea` still present; submitted text echoed escaped |

## D. Anonymous submission

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `POST /posts`, no session | 303, `Location: /login`; `create_post` never called |
| D2 | `GET /posts/new`, no session | 303, `Location: /login` |

## E. Guard delegation & routing

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `views_post.require_login` monkeypatched to a redirect response | Handler returns that response unchanged; `create_post` not called |
| E2 | `create_app()` dispatched `GET /posts/new` anonymous | 303 (real FP-003 guard), not 501 — placeholder replaced |
| E3 | `register(app)` on a fresh app | `GET /posts/new` and `POST /posts` resolve to `post_form` / `post_submit` |
| E4 | `GET /posts`, anonymous | still 405 with `Allow: POST` (only the POST handler is mounted) |

## F. Escaping

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Rejected content containing `<script>` | error page contains `&lt;script&gt;`, never a raw `<script>` tag |

## G. Exception contract

| # | Scenario | Expected |
|---|----------|----------|
| G1 | `create_post` raises the module `PostError` | Handler catches it and renders 200 with `str(exc)` |

Skeleton/test file: `tests/test_fp012_post_page.py`.
