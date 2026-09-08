# FP-001 Design: Web Application Skeleton

Task card: `input/tasks/social-media-platform/FP-001-web-skeleton.task.md` (sole spec).
Goal: Flask web foundation on top of the existing storage layer — application
factory `create_app()`, auto-registration of feature blueprints, base template
plus a home page, and a `python3 -m social_app.web` dev-server entry point.
No database access, no business logic (those are FP-002..FP-010).

## Approach

- New package `social_app/web/` (existing files untouched, including
  `social_app/db.py`):
  - `__init__.py` — `FEATURES = ("home",)` module-level tuple plus
    `create_app(features: Iterable[str] | None = None) -> Flask`.
  - `home.py` — `bp = Blueprint("home", __name__)` with `GET /` rendering
    `home/index.html`.
  - `__main__.py` — `python3 -m social_app.web` runs the Werkzeug dev server
    on `127.0.0.1:5000`; debug mode gated by `$SOCIAL_DEBUG` (truthy: "1",
    "true", "on" — case-insensitive).
  - `templates/base.html` (layout + nav + flash message region) and
    `templates/home/index.html` (extends base).
- `create_app` steps:
  1. `Flask(__name__)` — the package path puts the template folder at
     `social_app/web/templates/` automatically, matching the contract
     "templates live in `social_app/web/templates/<name>/`".
  2. `SECRET_KEY = os.environ.get("SOCIAL_SECRET_KEY", "dev-secret-key")`
     (signed-cookie sessions; default for dev/test only).
  3. For each name in `features` (default: module-level `FEATURES`):
     `importlib.import_module("social_app.web.<name>")` then
     `app.register_blueprint(module.bp)`. An unknown name re-raises as an
     `ImportError` whose message names the bad feature and hints at the fix —
     configuration errors surface at construction time, not first request.
  4. Global 404/500 handlers render simple error pages that extend
     `base.html`, so every response shares the layout including the flash
     region.

## Key decisions

1. **Feature auto-registration via importlib**: adding a feature later is one
   line (`FEATURES += ("<name>",)`-style tuple append) or an explicit
   `create_app(features=(...))` in tests — exactly the contract the card
   freezes for downstream tasks.
2. **No cross-blueprint `url_for`**: navigation and future cross-feature links
   are hard-coded path strings (`/`, `/login`, `/posts`, ...), keeping feature
   blueprints independently testable.
3. **Home page has no business data**: future entries (register / login /
   posts / friends) are listed as descriptions with grayed-out, non-link
   markers ("未上线"); each feature task will turn its entry into a real link
   by editing only `home/index.html`.
4. **`bp` presence is validated**: a feature module without a module-level
   `bp` raises a clear `ImportError` at factory time — same "fail early"
   rationale as unknown names.
5. **Existing pytest suite, `primes.py`, and repo hygiene untouched**; the
   card forbids modifying any existing file, so `ci.yml` is left as-is.

## Verification

`python3 -m pytest tests/test_web_skeleton.py -q`, full regression
`python3 -m pytest -q`, CLI smoke `python3 primes.py 50`.
Scenarios documented in `docs/test-cases/fp001-web-skeleton.md`.
