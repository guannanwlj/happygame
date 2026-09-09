# FP-004 Design: Preference Dimension Configuration

Task card: `input/tasks/itinerary-planner/FP-004-preference-config.task.md`
(sole spec). Goal: centralized, file-driven preference config —
`itinerary_app/preferences.json` (initial five dimensions + free-text item,
verbatim from card §3.2) plus `itinerary_app/prefs.py` exposing the S5
contract `load_preferences(config_path)` for FP-005 (form) and FP-007
(prompt building). Editing the JSON file changes behavior; code never
changes.

## Approach

- **Storage = data file.** No DB table (card §3.1): `preferences.json`
  ships inside `itinerary_app/`, next to the loader. Dimension set /
  labels are iterated by editing this file and restarting (§5: no hot
  reload required).
- **Loader contract.** `load_preferences(config_path: str | None = None)
  -> dict`: `config_path=None` resolves to the package-internal file via
  `Path(__file__).with_name("preferences.json")` (computed at call time,
  so it works from any CWD); an explicit path is read as-is. The file is
  parsed and validated on every call — no in-process cache, matching
  "改配置重启生效" and keeping tests hermetic.
- **One exception type.** `PreferenceConfigError(ValueError)` covers every
  unusable-config condition, each message carrying the reason (and the
  offending path / field location): missing file, invalid JSON, top level
  not an object, missing `dimensions` / `free_text`, wrong field types,
  empty `options`, duplicate dimension keys. Callers (FP-005 / FP-007)
  catch one type; the "不静默返回半成品" acceptance is guaranteed because
  validation happens before any data is returned.

## Key decisions

1. **Strict schema validation** (not just `dimensions` presence): every
   dimension must be an object with non-empty string `key`/`label` and a
   non-empty list of non-empty string `options`; `free_text` must be an
   object with non-empty string `key`/`label`/`placeholder`; dimension
   `key`s must be unique (form fields and prompt sections key off them).
   Missing `free_text` is an error, not a silent default — the §3.2 return
   structure promises it, and half-deleted configs should fail loudly.
2. **Unknown keys pass through.** Extra top-level/dimension fields are
   allowed (forward compatibility for validation-period iteration).
3. **Returned data is the parsed JSON as-is** (no rebuilding), so temp
   configs round-trip exactly — proving "改配置不改代码".
4. **No `__init__.py` re-export**: consumers import
   `itinerary_app.prefs` directly per the card's contract snippet; keeps
   the package surface stable for concurrent wave-1 tasks.

## Verification

`python3 -m pytest tests/test_fp004_prefs.py -q` (plus full suite).
Scenarios documented in `docs/test-cases/fp004-prefs.md`.
