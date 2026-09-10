# FP-010 Design: Follow Operation UI

Task card: `FP-010-follow-ui.task.md` (sole spec; body embedded in the work
order). Goal: expose the follow entry point as `POST /follow` and render a
result page — success feedback, or the readable reason when the request is
rejected (self-follow / unknown target / not logged in). Rule validation and
the write itself stay in FP-011 (`social_app/follow_service.py`).

## Approach

- One new module `social_app/views_follow.py` plus a one-line mount change in
  `social_app/app.py`'s `create_app()` (replace the FP-010 501 placeholder with
  `views_follow.register(app)`). No other runtime code changes.
- Public contract (card §3.3):

  ```python
  def follow_submit(request) -> Response   # POST /follow
  def register(app) -> None                # app.route("POST", "/follow", follow_submit)
  ```

- `follow_submit` flow, mirroring card §4:

  1. `denied = require_login(request)`; a non-`None` result is returned
     verbatim (anonymous callers get the 303 → `/login` redirect and no write
     is attempted).
  2. `fields = parse_form(request.body)`; `target_username = fields.get("target_username", "")`.
  3. `actor_id = current_user_id(request)`.
  4. `follow_service.follow(actor_id, target_username)`.
     - Success → `200` result page containing `关注成功` and a `返回首页` link.
     - `FollowError` → `200` result page containing the readable reason
       (`用户不存在` / `不能关注自己` / `未登录`) and the same home link.
  5. Every echoed value (the status message and the submitted target name) is
     passed through `html.escape`.

## Key decisions

1. **View owns rendering only.** The module calls `follow_service.follow` and
   renders its outcome; it never reads the `follows` table and never duplicates
   validation. This keeps FP-011 as the single source of follow rules.
2. **Monkeypatch-friendly imports (card §6).** `require_login` /
   `current_user_id` are imported by name into the view namespace, and the
   service is imported as a module (`from social_app import follow_service`)
   and called via `follow_service.follow`. Tests can therefore patch
   `social_app.views_follow.require_login` and `social_app.follow_service.follow`
   exactly as the card's mock strategy prescribes.
3. **Errors are rendered, not raised.** A `FollowError` is a user-facing
   rejection, so it becomes a `200` feedback page rather than a 4xx; only the
   missing-login path is a redirect (card §7).
4. **Escape at the boundary.** `html_response` already escapes the page title;
   the body fragments escape both the `FollowError` message and the
   user-supplied `target_username` so a crafted username can never inject HTML
   into the feedback page (card §5/§7).
5. **Deferred import in `create_app`.** `views_follow` imports from
   `social_app.app`, so `app.py` imports it inside `create_app()` to avoid a
   circular import at module load time.
6. **Idempotence is inherited.** Following an already-followed target is a
   no-op in FP-011 and therefore renders the same `关注成功` page — no special
   case in the view.

## Verification

`python3 -m pytest tests/test_fp010_follow_ui.py -q` (plus the full suite
`python3 -m pytest -q`). Scenarios documented in
`docs/test-cases/fp010-follow-ui.md`.
