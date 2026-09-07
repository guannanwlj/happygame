# FP-001 Design: Web Application Skeleton & Common Page Frame

Task card: `input/tasks/social-platform/FP-001-web-skeleton.task.md` (sole spec).
Goal: Flask application factory `create_app()`, common layout template
`templates/base.html`, and a 404 error page — the mounting point every later
page task (FP-003..FP-013) hooks into.

## Approach

- New module `social_app/app.py` exposing `create_app() -> Flask`. It does
  **not** touch `social_app/db.py` (no business tables read/written here).
- `create_app()` responsibilities per card §3.2:
  1. `app.secret_key = os.environ.get("SOCIAL_SECRET_KEY", "dev-secret")`
     (read at call time so tests can vary it) — required for Flask's signed
     cookie sessions used later by FP-003.
  2. Register a 404 error handler rendering `templates/404.html` with status
     404 — no white screen, no unhandled exception.
  3. Root route `GET /` → `redirect(url_for("feed.index"))`-style 302 to
     `/feed` (literal path, since the feed blueprint may not exist yet the
     redirect target is the path `/feed` itself, per the card).
  4. Optional blueprint registration driven by the module-level constant
     `BLUEPRINTS = [("social_app.auth", "bp"), ("social_app.friends", "bp"),
     ("social_app.feed", "bp")]`: import each module with `importlib`,
     fetch the attribute, and register; any `ImportError` or missing
     attribute is skipped silently so the skeleton starts while the other
     feature tasks are unimplemented.
- Templates live in the top-level `templates/` directory named by the card.
  Because `Flask(__name__)` would default to `social_app/templates`, the
  factory passes an explicit `template_folder` computed from `__file__`
  (``<repo>/templates``). `base.html` provides the header (site name +
  literal-path nav links `/login`, `/register`, `/feed`, `/friends`), the
  pending-count slot `{{ pending_count|default(0) }}`, and the
  `{% block content %}` extension point. `404.html` extends `base.html`.

## Key decisions

1. **Optional blueprint registration is data-driven**: the `BLUEPRINTS`
   constant is the single registry; later tasks just create their module
   with attribute `bp` and it gets picked up automatically on the next
   `create_app()` — no edits to this file needed.
2. **`(ImportError, AttributeError)` catch scope only**: unexpected
   real errors inside an *existing* blueprint module still propagate;
   only "module missing" / "attribute missing" are tolerated (skeleton
   must start when features are unimplemented, per card §3.2).
3. **302 (not 301) root redirect**: `redirect("/feed")` defaults to 302,
   matching the acceptance wording and staying cache-friendly.
4. **No auth anywhere**: per card §5 the skeleton performs no session or
   access control; `secret_key` is set purely as infrastructure.
5. **`pending_count` uses `|default(0)`**: pages never need to pass the
   variable; later tasks (FP-011) may inject it via a context processor.

## Verification

`python3 -m pytest tests/test_fp001_web_skeleton.py -q` (plus full suite).
Scenarios documented in `docs/test-cases/fp001-web-skeleton.md`.
