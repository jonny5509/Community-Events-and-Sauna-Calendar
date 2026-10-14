"""Tests for persistent attendance reminder helpers."""
from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.chastity_calendar.attendance import _event_id, _parse_start


def test_event_id_is_stable_for_same_occurrence():
    start = datetime(2026, 11, 5, 18, tzinfo=ZoneInfo("Europe/London"))
    assert _event_id("Fetish Night", start) == _event_id("Fetish Night", start)


def test_different_occurrences_have_different_ids():
    first = datetime(2026, 11, 5, 18, tzinfo=ZoneInfo("Europe/London"))
    second = datetime(2026, 11, 12, 18, tzinfo=ZoneInfo("Europe/London"))
    assert _event_id("Fetish Night", first) != _event_id("Fetish Night", second)


def test_event_url_does_not_change_occurrence_identity():
    start = datetime(2026, 11, 5, 18, tzinfo=ZoneInfo("Europe/London"))
    assert _event_id("Community Night", start, "https://example.com/a") == _event_id(
        "Community Night", start, "https://example.com/b"
    )


def test_parse_start_accepts_iso_datetime_with_timezone():
    parsed = _parse_start("2026-11-05T18:00:00+00:00")
    assert parsed.isoformat() == "2026-11-05T18:00:00+00:00"


def test_parse_start_accepts_iso_date():
    parsed = _parse_start("2026-11-05")
    assert parsed.hour == 0
    assert parsed.minute == 0
