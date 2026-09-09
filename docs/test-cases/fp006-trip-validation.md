# FP-006 Test Scenarios — Trip Input Validation (Itinerary Planner)

Module under test: `itinerary_app/validation.py::validate_trip_request`
(spec: task card FP-006 §3.2 S7 / §6 / §7 / §8). Pure function, dict in →
`list[str]` out; `[]` = pass, non-empty = block with locatable messages.

Seed data (card §6): legal `{"origin":"上海","destination":"成都",
"start_date":"2026-10-01","end_date":"2026-10-05"}`; invalid families —
end<start, 31-day span (2026-10-01~2026-10-31), 30-day boundary
(2026-10-01~2026-10-30), missing required fields, malformed dates
("2026/10/01", "2026-13-01").

## A. Acceptance — card §7

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Legal seed request | returns `[]` (pass, release for generation) |
| A2 | end_date 2026-09-30 < start_date 2026-10-01 | non-empty; contains 「返程日期不能早于开始日期」 |
| A3 | Span 31 days (2026-10-01~2026-10-31) | non-empty; message names the 30-day cap and advises splitting (拆分), mentions 31 |
| A4 | Span exactly 30 days (2026-10-01~2026-10-30) | `[]` (boundary included) |
| A5 | Each required field removed (4 cases) | non-empty; a 缺少 message names that exact field; no format/order/span noise for the removed field |
| A6 | start_date="2026/10/01" / "2026-13-01" | non-empty; format-class error naming start_date |

## B. Rule 1 — required fields

| # | Scenario | Expected |
|---|----------|----------|
| B1 | All four required fields removed | 4 distinct 缺少 errors, one per field |
| B2 | Each field set to `""` (empty string) | same as missing — 缺少 error names the field |
| B3 | Field set to `None` | treated as missing (defensive), 缺少 error |
| B4 | origin/destination present (any non-empty string) | never a 缺少 error for them |

## C. Rule 2 — date format

| # | Scenario | Expected |
|---|----------|----------|
| C1 | "2026-1-1" (unpadded), "20261001" (basic ISO), "not-a-date" | format error for that field (shape ≠ YYYY-MM-DD) |
| C2 | "2026-02-30" (illegal calendar date) | format error (fromisoformat rejects) |
| C3 | Both dates malformed | two format errors, one per field |
| C4 | Format error message echoes the offending raw value | locatable (contains the literal bad string) |

## D. Rules 3 & 4 — order and span

| # | Scenario | Expected |
|---|----------|----------|
| D1 | start == end (1-day trip) | `[]` |
| D2 | end < start by many days (span would be negative) | only the order error — no span error, no crash |
| D3 | 29-day span (2026-10-01~2026-10-29) | `[]` |
| D4 | 32-day span (2026-09-30~2026-10-31) | span error mentions 32 |
| D5 | start_date missing, end_date valid | only the 缺少 start_date error — order/span silently skipped (no format error for a missing field) |
| D6 | start_date malformed, end_date valid | only the format error — order/span skipped, no duplicate 缺少 |
| D7 | Dates in the past (2020-01-01~2020-01-03) | `[]` — no future-date rule in the card口径 |

## E. preferences & shape

| # | Scenario | Expected |
|---|----------|----------|
| E1 | preferences present as dict (any contents) | ignored → `[]` |
| E2 | preferences with odd values / extra unknown keys | ignored, no effect on errors |
| E3 | Result type sanity | returns a `list` of `str` (non-empty case too) |

Test file: `tests/test_fp006_validation.py`.
