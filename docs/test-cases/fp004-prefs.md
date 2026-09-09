# FP-004 Test Scenarios — Preference Dimension Configuration

Module under test: `itinerary_app/prefs.py` + package data
`itinerary_app/preferences.json` (spec: task card FP-004 §3.2/§7/§8).
Temp configs are written to `tmp_path`; no repo files are mutated.

## A. Acceptance 1 — default load returns the full structure

| # | Scenario | Expected |
|---|----------|----------|
| A1 | `load_preferences()` (no argument) | Returns 5 dimensions with keys `budget, pace, interest, diet, transport` in card order; each has non-empty string `key`/`label` and a non-empty list of non-empty string `options` |
| A2 | Default free-text item | `free_text` equals `{"key": "notes", "label": "补充说明", "placeholder": "其他偏好或约束（选填）"}` (shipped file locked verbatim) |
| A3 | Default path resolution | `load_preferences(None)` == `load_preferences(str(DEFAULT_CONFIG_PATH))`; works from any CWD (path anchored to the module) |

## B. Acceptance 2 — config driven, not code driven

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Temp config copies the default then adds dimension 「同行人」 with new options, loaded via `load_preferences(path)` | 6 dimensions returned; the new key/label/options all present; original 5 intact |
| B2 | Temp config adjusts an existing dimension (label + options list changed) | New label and new options returned verbatim (old labels gone) |
| B3 | Temp config drops a dimension | Only the remaining dimensions returned — removal works without code change |

## C. Acceptance 3 + error/edge paths — invalid config fails loudly

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Config missing `dimensions` key | `PreferenceConfigError`; message names `dimensions` (acceptance: no silent half-result) |
| C2 | `dimensions` of wrong type (string / object) | `PreferenceConfigError` naming `dimensions` |
| C3 | `dimensions` empty list | `PreferenceConfigError` |
| C4 | A dimension missing `key`/`label`/`options` | `PreferenceConfigError` naming the field and its index |
| C5 | `key`/`label` wrong type (e.g. int) or empty string | `PreferenceConfigError` naming the field |
| C6 | `options` wrong type (string) or empty list | `PreferenceConfigError` naming `options` |
| C7 | An option item is not a non-empty string | `PreferenceConfigError` naming the option index |
| C8 | Duplicate dimension `key`s | `PreferenceConfigError` naming the duplicated key |
| C9 | Config missing `free_text`, or `free_text` malformed (not an object / missing `placeholder`) | `PreferenceConfigError` naming `free_text` and the problem |
| C10 | Top-level JSON is an array | `PreferenceConfigError` |
| C11 | File content is not valid JSON | `PreferenceConfigError` (wrapped, not raw `json.JSONDecodeError`) |
| C12 | Explicit path does not exist | `PreferenceConfigError` containing the path (not raw `FileNotFoundError`) |
| C13 | Exception taxonomy | `PreferenceConfigError` subclasses `ValueError` |

Skeleton/test file: `tests/test_fp004_prefs.py`.
