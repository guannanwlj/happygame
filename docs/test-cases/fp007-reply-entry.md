# FP-007 Test Scenarios — Reply Entry Point

Module under test: `social_app/views_feed.py` (`_render_reply_form`,
`_render_replies`, `_render_comment`) via the home feed `GET /`
(spec: task card FP-007 §2–§8).

Isolation (card §6): tests monkeypatch `views_feed.require_login`,
`views_feed.current_user_id` and `views_feed.get_feed` with contract-shaped
stub rows and dispatch `GET /` through `create_app()`; no database is touched.

Seed data (card §6): top-level comment `c1` (`parent_id=None`, author `alice`,
content `top`) and replies `c2` (`older`, `2026-01-01T01:00:00Z`) and `c3`
(`newer`, `2026-01-01T02:00:00Z`), both with `parent_id=1`.

## A. Acceptance 1 — reply entry point on top-level comments

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Top-level comment rendered | A `<form class="reply-form">` with `action="/comments/1/replies"` and `method="post"` |
| A2 | Reply form fields | `<textarea name="content">` and a submit button labelled `回复` |
| A3 | Comment without replies | The reply form still renders (entry point is independent of existing replies) |

## B. Acceptance 2 — nested, ascending replies

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Two replies to `c1` | Both render inside `<ul class="reply-list">` under the parent `<li class="comment">` |
| B2 | `older` before `newer` (as delivered by the caller) | `older` index < `newer` index; parent content index < reply indices |
| B3 | Multiple parents | Each parent gets its own `reply-list` |

## C. Acceptance 3 — one level only

| # | Scenario | Expected |
|---|----------|----------|
| C1 | A reply entry | No `reply-form` and no `reply-list` under the reply |
| C2 | One parent + two replies | Exactly one `class="reply-form"` and one `reply-list` in the body |

## D. Acceptance 4 — escaping

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Reply content `<script>alert(1)</script>` | Raw tag absent; `&lt;script&gt;alert(1)&lt;/script&gt;` present |
| D2 | Reply author `<b>eve</b>` / time `<i>t</i>` | Raw tags absent; escaped forms present |
| D3 | Top-level `comment_id` from a `SimpleNamespace` row | Form action rendered from the attribute value |

## E. Edge cases / compatibility

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Legacy comment dict without `comment_id` / `parent_id` | Renders as top-level (200) with a reply form; no crash, no `reply-list` |
| E2 | FP-009 monkeypatches `_render_reply_form` / `_render_replies` | The module globals are overridden (non-regression with the FP-009 suite) |

Skeleton/test file: `tests/test_fp007_reply_entry.py`.
