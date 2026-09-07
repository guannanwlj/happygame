# FP-001 Test Scenarios: Web Application Skeleton & Common Page Frame

Source: task card `FP-001-web-skeleton` §7 acceptance criteria + §8 suggested
tests. Suite: `tests/test_fp001_web_skeleton.py`.

Fixture strategy (card §6): the feature blueprints (`social_app.auth`,
`social_app.friends`, `social_app.feed`) do not exist yet, so every test runs
against a bare `create_app()` — which is itself the "blueprints missing"
acceptance path. A temporary demo blueprint/route is registered inside tests
to verify "a registered route returns HTML wrapped in the common layout".

## S1 — Registered route renders through base.html (acceptance 1)

- S1.1 Given `create_app()` built the app (feature blueprints skipped) When
  hitting a registered demo route Then status 200, content-type HTML, body
  contains the header marker (site name), the four nav links `/login`
  `/register` `/feed` `/friends`, and the demo content from the
  `{% block content %}`.
- S1.2 The pending-count slot renders as `0` when the page passes no
  `pending_count` (default filter).
- S1.3 A page may override `pending_count`; the header shows that value
  (slot is wired, not hardcoded).

## S2 — Unknown path returns rendered 404 page (acceptance 2)

- S2.1 Given the built app When requesting a non-existent path Then status
  404, HTML body contains 404-page copy, and — no white screen — the common
  layout markers are present (404.html extends base.html).
- S2.2 A second distinct unknown path also 404s (handler is generic, not
  route-specific).

## S3 — Root redirects to /feed (acceptance 3)

- S3.1 `GET /` → status 302 with `Location` ending in `/feed`.
- S3.2 Following the redirect yields a handled response (the redirect
  target itself is outside this skeleton's scope — only the 302 + target
  path are asserted; the target currently 404s, which is fine at this
  wave).

## S4 — Skeleton robustness (acceptance 1 precondition, card §3.2)

- S4.1 `create_app()` raises nothing while all three feature modules are
  missing (skip mechanism works); app has the root route and 404 handler
  registered.
- S4.2 If a module exists but lacks the `bp` attribute it is skipped
  (missing-attribute tolerance) — verified via a stub module injected into
  `sys.modules`.
- S4.3 `secret_key` is taken from `$SOCIAL_SECRET_KEY` when set, and
  defaults to `dev-secret` when unset.
- S4.4 Repeated `create_app()` calls return independent app instances
  (factory is repeatable; no cross-test leakage).
