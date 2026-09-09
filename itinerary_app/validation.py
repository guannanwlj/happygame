"""Trip request validation rules (FP-006, provider of the S7 contract).

`validate_trip_request` is the first gate of the generation flow (FP-009
calls it right after form submission): a pure, stateless rule function —
dict in, ``list[str]`` of human-readable errors out. An empty list releases
the request for LLM generation; any entry blocks the submission.

Rules (card §3.2 S7, wording/parameters fixed upstream):
1. required   — origin / destination / start_date / end_date missing or
                empty → one 「缺少…」 message per field;
2. format     — dates must be YYYY-MM-DD and legal calendar dates;
3. order      — end_date must not precede start_date;
4. span       — (end − start).days + 1 must not exceed 30 days;
5. single     — a non-empty-string destination counts as single (empty
                values fall back to rule 1's 缺少 message).
"""

import datetime
import re

MAX_TRIP_DAYS = 30

#: Required fields → Chinese label used in the 「缺少…」 messages.
REQUIRED_FIELDS: dict[str, str] = {
    "origin": "出发地",
    "destination": "目的地",
    "start_date": "开始日期",
    "end_date": "返程日期",
}

DATE_FIELDS = ("start_date", "end_date")

# Strict YYYY-MM-DD shape. `date.fromisoformat` alone is not enough on
# Python ≥3.11 (it also accepts basic ISO forms like "20261001"), while the
# card pins the format to the dashed, zero-padded form.
_ISO_DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_blank(value: object) -> bool:
    """Rule-1 sense of missing: absent, None, non-string, or empty string."""
    return not isinstance(value, str) or value == ""


def _parse_date(raw: object) -> datetime.date | None:
    """Parse a field as YYYY-MM-DD; return None if not a legal date."""
    if not isinstance(raw, str) or not _ISO_DATE_SHAPE.match(raw):
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


def validate_trip_request(req: dict) -> list[str]:
    """Validate one trip request; [] passes, any entry blocks submission.

    req = {"origin": str, "destination": str,
           "start_date": str, "end_date": str,
           "preferences": dict (optional, contents not validated here)}
    """
    errors: list[str] = []

    # Rule 1 — required fields present and non-empty.
    for field, label in REQUIRED_FIELDS.items():
        if _is_blank(req.get(field)):
            errors.append(f"缺少{label}（{field}）")

    # Rule 2 — date format (only for dates that are actually present).
    parsed: dict[str, datetime.date] = {}
    for field in DATE_FIELDS:
        raw = req.get(field)
        if _is_blank(raw):
            continue  # already reported by rule 1
        date = _parse_date(raw)
        if date is None:
            errors.append(
                f"{field} 日期格式非法：{raw!r}，应为 YYYY-MM-DD 的合法日期"
            )
        else:
            parsed[field] = date

    # Rules 3 & 4 — order and span, only computable with both dates valid.
    if len(parsed) == len(DATE_FIELDS):
        start, end = parsed["start_date"], parsed["end_date"]
        if end < start:
            errors.append(
                f"返程日期不能早于开始日期（start_date={start.isoformat()}，"
                f"end_date={end.isoformat()}）"
            )
        else:
            span_days = (end - start).days + 1
            if span_days > MAX_TRIP_DAYS:
                errors.append(
                    f"行程跨度 {span_days} 天，超过 {MAX_TRIP_DAYS} 天上限，"
                    "建议拆分为多段行程"
                )

    return errors
