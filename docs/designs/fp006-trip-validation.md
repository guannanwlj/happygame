# FP-006 Design: Trip Input Validation (Itinerary Planner)

Task card: `input/tasks/itinerary-planner/FP-006-trip-validation.task.md`
(sole spec, embedded in the work order). Goal: the S7 validation contract
provider `itinerary_app/validation.py::validate_trip_request(req)` — a pure
rule function the generation flow (FP-009) calls before any LLM work; a
non-empty error list blocks the submission.

## Approach

- One new module `itinerary_app/validation.py`, no other runtime code
  touched (the form-page rendering is FP-005's weak-integration concern).
- Pure function, no I/O / no state / stdlib only:

  ```python
  def validate_trip_request(req: dict) -> list[str]:
      # req = {"origin": str, "destination": str,
      #         "start_date": str, "end_date": str,
      #         "preferences": dict (optional, contents not validated)}
  ```

  `[]` = pass (release for generation); non-empty = human-readable,
  locatable error strings that block submission.

- Rules checked in card order, errors accumulated (not first-fail) so the
  form can surface every problem at once:
  1. **Required** — `origin` / `destination` / `start_date` / `end_date`
     absent, `None`, or `""` → one `缺少 <field>（<中文名>）` per field.
  2. **Date format** — present date fields must parse as `YYYY-MM-DD` and
     be a legal calendar date (`datetime.date.fromisoformat`).
  3. **Order** — both dates parsed and `end_date < start_date` → the card
     wording 「返程日期不能早于开始日期」 plus both dates for locatability.
  4. **Span** — `（end − start).days + 1 > 30` → error naming the actual
     day count, the 30-day cap, and the advice to split the trip
     (30 days passes, 31 fails).
  5. **Single destination** — folded into rule 1: a non-empty string
     destination is "single"; empty goes to the 缺少 message.

## Key decisions

1. **Skip dependent checks, never fake them** — rules 3/4 need both dates
   parsed. If a date is missing or malformed, only rules 1/2 fire; no
   misleading order/span errors and no exceptions. Likewise span is only
   evaluated when `end >= start` (an inverted range already failed rule 3).
2. **Two-stage date parse** — a `^\d{4}-\d{2}-\d{2}$` shape check, then
   `date.fromisoformat` for calendar legality. Reason: Python ≥3.11's
   `fromisoformat` also accepts basic ISO forms like `"20261001"`, which
   violate the card's literal `YYYY-MM-DD` format; the regex keeps the
  口径 strict while the card's named parser stays the legality authority
   (it rejects `2026-13-01`, `2026-02-30`, …).
3. **Accumulate, don't short-circuit** — the caller (FP-005 form) wants the
   full picture; each rule appends at most its own message(s).
4. **Locatable copy** — every message names the offending field/value:
   missing → field key + Chinese label; format → field + echoed raw value;
   order → both dates; span → computed day count + the 30 cap.
5. **No future-date rule** — the card defines none; past dates validate
   purely on format/order/span. Locked by a test so later features must
   add it consciously, not by drift.
6. **Literal empty check** — 「缺失或空串」 means absent / `None` / `""`;
   whitespace-only strings are NOT rewritten or stripped (no hidden口径
   change). `preferences` is accepted and ignored entirely.

## Verification

`python3 -m pytest tests/test_fp006_validation.py -q` (plus the full
suite). Scenarios documented in `docs/test-cases/fp006-trip-validation.md`.
