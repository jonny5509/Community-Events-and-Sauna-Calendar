"""Regression tests for routing discovered events to separate calendars."""
from datetime import date, datetime
from types import SimpleNamespace

from custom_components.chastity_calendar.calendar import ChastityChallengeCalendar


def _event(summary, category, categories):
    start = datetime(2027, 6, 12)
    return {
        "summary": summary,
        "start": start,
        "end": datetime(2027, 6, 13),
        "description": "Test event",
        "category": category,
        "categories": categories,
        "location": "",
    }


def _summaries(calendar_type, events):
    calendar = ChastityChallengeCalendar(SimpleNamespace(data=events), calendar_type)
    return {event.summary for event in calendar._events_between(date(2027, 6, 1), date(2027, 7, 1))}


def test_lgbtq_events_are_separate_from_monthly_calendar():
    events = [
        _event("Gay social meetup", "gay", ["gay", "lgbtq"]),
        _event("General community fair", "community", ["community"]),
        _event("Sauna theme night", "sauna", ["sauna"]),
    ]

    monthly = _summaries("monthly", events)
    assert "General community fair" in monthly
    assert "Gay social meetup" not in monthly
    assert "Sauna theme night" not in monthly
    lgbtq = _summaries("pride", events)
    assert "Gay social meetup" in lgbtq
    assert "Pride Month" in lgbtq
    assert "General community fair" not in lgbtq
    assert "Sauna theme night" not in lgbtq
    sauna = _summaries("sauna", events)
    assert "Sauna theme night" in sauna
    assert "Gay social meetup" not in sauna
    assert "General community fair" not in sauna


def test_lgbtq_sauna_event_can_appear_in_both_focused_calendars():
    event = _event("Queer sauna social", "sauna", ["sauna", "queer", "lgbtq"])

    assert "Queer sauna social" not in _summaries("monthly", [event])
    assert "Queer sauna social" in _summaries("pride", [event])
    assert "Queer sauna social" in _summaries("sauna", [event])



def test_timed_discovered_events_are_timezone_aware():
    """Naive source datetimes must not make Home Assistant reject CalendarEvent."""
    event = _event("Sauna session", "sauna", ["sauna"])
    sauna = ChastityChallengeCalendar(SimpleNamespace(data=[event]), "sauna")
    result = sauna._events_between(date(2027, 6, 1), date(2027, 7, 1))

    assert len(result) == 1
    assert result[0].start.tzinfo is not None
    assert result[0].end.tzinfo is not None


def test_mixed_all_day_and_timed_events_sort_without_type_error():
    """All-day dates and timed datetimes can coexist in one calendar result."""
    events = [
        _event("Timed sauna session", "sauna", ["sauna"]),
        {
            "summary": "All-day sauna event",
            "start": date(2027, 6, 14),
            "end": date(2027, 6, 15),
            "description": "All day",
            "category": "sauna",
            "categories": ["sauna"],
            "location": "",
        },
    ]
    sauna = ChastityChallengeCalendar(SimpleNamespace(data=events), "sauna")
    result = sauna._events_between(date(2027, 6, 1), date(2027, 7, 1))

    assert {event.summary for event in result} == {"Timed sauna session", "All-day sauna event"}



def test_mixed_date_and_naive_datetime_endpoints_are_normalized():
    """A mixed endpoint pair must still satisfy Home Assistant's schema."""
    event = {
        "summary": "Sauna session with date end",
        "start": datetime(2027, 6, 12, 19, 30),
        "end": date(2027, 6, 13),
        "description": "Test event",
        "category": "sauna",
        "categories": ["sauna"],
        "location": "",
    }
    sauna = ChastityChallengeCalendar(SimpleNamespace(data=[event]), "sauna")
    result = sauna._events_between(date(2027, 6, 1), date(2027, 7, 1))

    assert len(result) == 1
    assert result[0].start.tzinfo is not None
    assert result[0].start.utcoffset() is not None
    assert result[0].end.tzinfo is not None
    assert result[0].end.utcoffset() is not None



def test_verified_crown_days_appear_only_on_monthly_calendar():
    coordinator = SimpleNamespace(data=[], crown_days={"2027-06-12"})
    monthly = ChastityChallengeCalendar(coordinator, "monthly")
    monthly_events = monthly._events_between(date(2027, 6, 1), date(2027, 7, 1))
    crowns = [event for event in monthly_events if "participation crown" in event.summary]

    assert len(crowns) == 1
    assert crowns[0].summary == "👑 Summer Chastity Challenge participation crown"
    assert crowns[0].start == date(2027, 6, 12)
    assert crowns[0].end == date(2027, 6, 13)

    sauna = ChastityChallengeCalendar(coordinator, "sauna")
    sauna_events = sauna._events_between(date(2027, 6, 1), date(2027, 7, 1))
    assert not any("participation crown" in event.summary for event in sauna_events)
