"""FP-006 tests: trip input validation (itinerary_app.validation).

Scenarios documented in docs/test-cases/fp006-trip-validation.md. The module
under test is a pure rule function: dict in -> list[str] out, [] = pass.
"""

import pytest

from itinerary_app.validation import validate_trip_request


def legal_request(**overrides) -> dict:
    """Card §6 legal seed sample with per-test overrides applied."""
    request = {
        "origin": "上海",
        "destination": "成都",
        "start_date": "2026-10-01",
        "end_date": "2026-10-05",
    }
    request.update(overrides)
    return request


class TestLegalRequests:
    """A1, A4, D1, D3, D7, E1: well-formed requests pass with []."""

    def test_legal_seed_sample_passes(self):
        assert validate_trip_request(legal_request()) == []

    def test_span_exactly_30_days_passes(self):
        assert validate_trip_request(
            legal_request(end_date="2026-10-30")
        ) == []

    def test_span_29_days_passes(self):
        assert validate_trip_request(
            legal_request(end_date="2026-10-29")
        ) == []

    def test_same_day_trip_passes(self):
        assert validate_trip_request(
            legal_request(start_date="2026-10-01", end_date="2026-10-01")
        ) == []

    def test_past_dates_pass_no_future_rule(self):
        assert validate_trip_request(
            legal_request(start_date="2020-01-01", end_date="2020-01-03")
        ) == []

    def test_preferences_dict_is_ignored(self):
        assert validate_trip_request(
            legal_request(preferences={"pace": "慢", "tags": [1, None]})
        ) == []


class TestMissingRequired:
    """A5, B1, B2, B3: rule 1 — absent / empty / None required fields."""

    @pytest.mark.parametrize(
        "field", ["origin", "destination", "start_date", "end_date"]
    )
    def test_missing_field_named_in_error(self, field):
        request = legal_request()
        del request[field]
        errors = validate_trip_request(request)
        assert errors
        assert any("缺少" in e and field in e for e in errors)

    def test_empty_string_counts_as_missing(self):
        errors = validate_trip_request(legal_request(origin=""))
        assert any("缺少" in e and "origin" in e for e in errors)

    def test_none_counts_as_missing(self):
        errors = validate_trip_request(legal_request(destination=None))
        assert any("缺少" in e and "destination" in e for e in errors)

    def test_all_four_missing_gives_four_errors(self):
        errors = validate_trip_request(
            {"preferences": {}}
        )
        assert len(errors) == 4
        for field in ("origin", "destination", "start_date", "end_date"):
            assert any(field in e for e in errors)

    def test_missing_date_skips_order_and_span(self):
        """D5: no format error for a missing date, no misleading errors."""
        request = legal_request()
        del request["start_date"]
        errors = validate_trip_request(request)
        assert errors
        assert not any("格式" in e for e in errors)
        assert not any("早于" in e or "跨度" in e for e in errors)


class TestDateFormat:
    """A6, C1–C4: rule 2 — YYYY-MM-DD shape + legal calendar date."""

    @pytest.mark.parametrize(
        "bad_date",
        [
            "2026/10/01",  # wrong separator (card seed)
            "2026-13-01",  # month 13 (card seed)
            "2026-02-30",  # illegal calendar date
            "2026-1-1",  # unpadded
            "20261001",  # basic ISO — accepted by fromisoformat, not YYYY-MM-DD
            "not-a-date",
        ],
    )
    def test_malformed_date_gives_format_error(self, bad_date):
        errors = validate_trip_request(legal_request(start_date=bad_date))
        assert errors
        assert any("start_date" in e and "格式" in e for e in errors)

    def test_format_error_echoes_offending_value(self):
        errors = validate_trip_request(
            legal_request(start_date="2026/10/01")
        )
        assert any("2026/10/01" in e for e in errors)

    def test_both_dates_malformed_gives_two_errors(self):
        errors = validate_trip_request(
            legal_request(start_date="x", end_date="y")
        )
        assert len(errors) == 2

    def test_malformed_date_skips_order_and_span(self):
        """D6: dependent checks are skipped, no duplicate 缺少 error."""
        errors = validate_trip_request(legal_request(end_date="2026/10/05"))
        assert errors
        assert not any("缺少" in e for e in errors)
        assert not any("早于" in e or "跨度" in e for e in errors)


class TestDateOrder:
    """A2, D2: rule 3 — end_date must not precede start_date."""

    def test_end_before_start_rejected(self):
        errors = validate_trip_request(
            legal_request(end_date="2026-09-30")
        )
        assert "返程日期不能早于开始日期" in " ".join(errors)

    def test_order_error_is_locatable(self):
        errors = validate_trip_request(
            legal_request(start_date="2026-10-01", end_date="2026-09-30")
        )
        assert any("2026-10-01" in e and "2026-09-30" in e for e in errors)

    def test_inverted_range_gives_no_span_error(self):
        errors = validate_trip_request(
            legal_request(end_date="2020-09-30")
        )
        assert len(errors) == 1
        assert not any("跨度" in e for e in errors)


class TestTripSpan:
    """A3, D4: rule 4 — span cap of 30 days, split advice."""

    def test_span_31_days_rejected(self):
        errors = validate_trip_request(
            legal_request(end_date="2026-10-31")
        )
        assert errors
        joined = " ".join(errors)
        assert "跨度" in joined
        assert "31" in joined
        assert "30" in joined
        assert "拆分" in joined

    def test_span_32_days_error_mentions_actual_days(self):
        errors = validate_trip_request(
            legal_request(start_date="2026-09-30", end_date="2026-10-31")
        )
        assert any("32" in e for e in errors)


class TestResultShape:
    """E3: contract shape sanity."""

    def test_pass_returns_empty_list_type(self):
        result = validate_trip_request(legal_request())
        assert isinstance(result, list)
        assert result == []

    def test_fail_returns_list_of_str(self):
        result = validate_trip_request({})
        assert isinstance(result, list)
        assert result
        assert all(isinstance(message, str) for message in result)
