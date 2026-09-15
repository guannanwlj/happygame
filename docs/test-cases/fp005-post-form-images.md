# FP-005 Test Scenarios — Post Form Image Selection

Module under test: `social_app/views_post.py` (`_FORM_TEMPLATE` markup only;
spec: task card FP-005 §4/§7/§8). Requests are dispatched in-process through
the real `create_app()` registry. Per card §6 the login state is **real**:
each test seeds one `users` row into a fresh temporary database
(`SOCIAL_DB`) and obtains a token via `session.create_session(uid)`; no
guard stubbing. The §7 rejection scenario monkeypatches
`social_app.posts.create_post` to raise `PostError("图片数量不能超过 9 张")`
(any rejection reason) and posts a urlencoded body the existing handler
already parses.

## A. Acceptance — logged-in rendering (card §7 case 1)

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Seeded user `GET /posts/new` with real session cookie | 200, HTML page whose `<form>` tag carries `enctype="multipart/form-data"` |
| A2 | Same page | Contains an `<input type="file" ... multiple>` control with `id="images"`, `name="images"`, and `accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"` (three formats + webp) |
| A3 | Same page | Labels wired: `<label for="images">图片</label>` for the picker |

## B. Acceptance — rejection re-render (card §7 case 2)

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Logged-in `POST /posts` (urlencoded `content=hello`), `create_post` monkeypatched to raise `PostError("图片数量不能超过 9 张")` | 200 (no redirect), body contains `<p class="error">图片数量不能超过 9 张</p>` |
| B2 | Same response | Textarea refills the submitted text: `>hello</textarea>` present |
| B3 | Same response | Re-rendered form keeps `enctype` and the file input (user can retry) |

## C. Acceptance — login guard (card §7 case 3)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Anonymous `GET /posts/new` (no cookie) | 303, `Location: /login`; form not rendered |

## D. Acceptance — regression of existing elements (card §7 case 4)

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Logged-in `GET /posts/new` | `<textarea` with `name="content"` still present |
| D2 | Same page | `action="/posts"` + `method="post"` preserved |
| D3 | Same page | `<button type="submit">发布</button>` preserved |

## E. Edge cases (retained-mechanism hardening)

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Rejected submit with `content=%3Cscript%3E` (monkeypatched rejection) | Textarea echoes `&lt;script&gt;`; no raw `<script>` tag in the page |
| E2 | Session store isolation | Every test clears `session._sessions` before/after (process-wide FP-003 store), so tokens never leak across tests |

Skeleton/test file: `tests/test_fp005_post_form_images.py`.
