"""Regression tests for explicit dates extracted from public RSS results."""

from datetime import datetime

from custom_components.chastity_calendar.discovery import _find_future_date


TODAY = datetime(2026, 10, 12)


def test_extracts_month_day_year() -> None:
    result = _find_future_date("Pride festival June 26, 2027", TODAY)

    assert result == datetime(2027, 6, 26)


def test_extracts_day_month_year() -> None:
    result = _find_future_date("Parade on 26 June 2027", TODAY)

    assert result == datetime(2027, 6, 26)


def test_extracts_iso_date() -> None:
    result = _find_future_date("Event date: 2027-06-26", TODAY)

    assert result == datetime(2027, 6, 26)


def test_extracts_start_of_date_range() -> None:
    result = _find_future_date("Festival runs June 26–27, 2027", TODAY)

    assert result == datetime(2027, 6, 26)


def test_ignores_invalid_calendar_date() -> None:
    result = _find_future_date("Event date: February 31, 2027", TODAY)

    assert result is None


def test_ignores_past_date() -> None:
    result = _find_future_date("Event was June 26, 2026", TODAY)

    assert result is None


def test_ignores_dates_beyond_two_year_window() -> None:
    result = _find_future_date("Event date: 2029-01-01", TODAY)

    assert result is None


def test_returns_earliest_eligible_date() -> None:
    result = _find_future_date(
        "Announcement mentions July 10, 2027 and June 26, 2027",
        TODAY,
    )

    assert result == datetime(2027, 6, 26)
