# FP-004 Design: 用户注册（User Registration）

## Spec situation (important)

The task card `input/tasks/social-platform/FP-004-user-registration.task.md` is
**absent** from this branch and from every branch in the repository (verified
via `git ls-tree -r` across all refs). Per the wave instructions the card is
the sole spec, so this design reconstructs the FP-004 contract from the
authoritative cross-references that do exist in-repo:

1. **FP-003 card** (branch `task/task-mtqye2a3-c04`,
   `input/tasks/social-platform/FP-003-auth-session.task.md`) §5:
   “不做注册页/登录页界面与表单流程（由 **FP-004 用户注册**、FP-005 用户登录与登出
   负责），本任务只提供其调用的哈希/会话能力” → FP-004 owns the **registration
   page + form flow**, consuming the FP-003 auth contract.
2. **FP-003 card §3.2** embeds the auth contract in full
   (`hash_password` / `verify_password` / session helpers / `login_required`),
   including the exact stored-hash format
   `pbkdf2:sha256$<iterations>$<salt_hex>$<hash_hex>`. FP-004 is listed as a
   consumer of it.
3. **FP-002 skeleton contract** (branch `task/task-mtqye2a3-c02`):
   `create_app()` mounts feature **blueprints** named `bp` per module; the
   source comment literally names `from . import register;
   app.register_blueprint(register.bp)` as the FP-004 integration point, and
   the nav bar links `/register`.
4. **Platform rules**: credentials are 用户名+密码 (D-004); 密码绝不以明文落盘;
   `users` table comes from FP-001 (`username UNIQUE`, `password_hash`).

Every decision below that the missing card would have pinned is flagged as an
**assumption** and kept deliberately conventional.

## Approach

- New module `social_app/register.py` exposing `bp = Blueprint("register",
  __name__)` with a single view on `/register` (GET form, POST submit) — the
  mounting convention FP-002's `register_blueprints` registry expects.
- Registration flow (all server-rendered Jinja, matching the FP-002 skeleton):
  - `GET /register` → 200 HTML form (`username`, `password` inputs).
  - `POST /register` valid → `INSERT INTO users` via FP-001 `db.execute`
    with `auth.hash_password(password)`; `flash` a success message; 302 to
    `/login` (login page itself is FP-005; 404 until it merges, same as the
    FP-002 “挂载前 404 属预期” note).
  - invalid/duplicate → re-render the form with the error message and the
    submitted username preserved (Jinja autoescaping makes the echo XSS-safe).
- Validation rules (**assumption** — card absent; conventional bounds):
  - username: stored `strip()`ed; must be 3–30 chars of `[A-Za-z0-9_]`;
  - password: taken verbatim (never stripped), length 6–128;
  - duplicate username checked via a pre-select for a friendly message, with
    the SQLite `UNIQUE` violation (`sqlite3.IntegrityError`) caught as a
    race-condition backstop → same “already taken” error.
- **No auto-login** after registration (**assumption**): session
  establishment belongs to FP-005 (登录与登出), so FP-004 hands over to
  `/login`. Error responses re-render with status 200 (Flask tutorial
  convention for form flows).

## Key decisions

1. **`social_app/auth.py` is added as a self-built dependency stand-in.**
   FP-003 is not merged into this branch. The wave instruction says to
   self-build unmerged dependencies per the task-card §3 embedded contract;
   the FP-003 card §3.2 pins the full auth API and hash format. To guarantee
   contract compliance *and* a conflict-free merge when the FP-003 branch
   lands, the stand-in is the byte-identical realization of that contract
   (taken from the FP-003 feature branch). Only `hash_password` is consumed
   by FP-004; the rest of the contract ships along so the module is complete.
2. **`social_app/templates/base.html` likewise** is the FP-002 stand-in
   (byte-identical to the FP-002 branch file): `register.html` extends it
   (`title` / `content` blocks, flashed-messages region, nav links). Same
   conflict-free-merge rationale. `index.html` is *not* copied — FP-004 never
   renders it.
3. **Tests self-build the minimal Flask shell instead of `create_app()`**
   (FP-002 absent, mirroring the FP-003 card §6 mock strategy): the fixture
   builds `Flask("social_app")` — import-name resolution points the template
   loader at `social_app/templates/` — registers `register.bp`, and uses
   `TESTING=True` + a test `SECRET_KEY`.
4. **DB isolation** follows the established FP-001/FP-003 pattern: an
   autouse fixture points `SOCIAL_DB` at a fresh `tmp_path` file and runs
   `init_db()`, so no test can touch the repo's default
   `social_platform.db`.
5. **User-visible messages are exported constants** (`USERNAME_REQUIRED`,
   `USERNAME_INVALID`, `USERNAME_TAKEN`, `PASSWORD_INVALID`,
   `SUCCESS_MESSAGE`) so tests assert against the API, not string literals
   duplicated in the test file.
6. **requirements.txt** (flask>=3.0, byte-identical to the FP-002 branch
   file) records the Flask dependency the branch now carries.

## Verification

`python3 -m pytest -q` (full suite, blocking). FP-004 scenarios documented in
`docs/test-cases/fp004-user-registration.md`; tests in
`tests/test_fp004_register.py`.
