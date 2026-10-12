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
