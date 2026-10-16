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
    calendar = ChastityChallengeCalendar(SimpleNamespace(data=events), calendar_type, "test-entry")
    return {event.summary for event in calendar._events_between(date(2027, 6, 1), date(2027, 7, 1))}


def test_lgbtq_events_are_separate_from_monthly_calendar():
    events = [
        _event("Gay social meetup", "gay", ["gay", "lgbtq"]),
        _event("General community fair", "community", ["community"]),
    ]

    monthly = _summaries("monthly", events)
    assert "General community fair" in monthly
    assert "Gay social meetup" not in monthly
    lgbtq = _summaries("pride", events)
    assert "Gay social meetup" in lgbtq
    assert "Pride Month" in lgbtq
    assert "General community fair" not in lgbtq


def test_lgbtq_kink_event_appears_only_in_kink_calendar():
    event = _event("Queer BDSM Social", "community", ["community", "queer", "lgbtq", "kink"])

    assert "Queer BDSM Social" not in _summaries("monthly", [event])
    assert "Queer BDSM Social" not in _summaries("pride", [event])
    assert "Queer BDSM Social" in _summaries("kink", [event])


def test_lgbtq_only_event_remains_in_pride_calendar():
    event = _event("Queer Film Night", "community", ["community", "queer", "lgbtq"])

    assert "Queer Film Night" not in _summaries("monthly", [event])
    assert "Queer Film Night" in _summaries("pride", [event])
    assert "Queer Film Night" not in _summaries("kink", [event])



def test_lgbtq_identity_events_are_routed_by_listing_text_without_category_tags():
    events = [
        _event("Pansexual community meetup", "community", ["community"]),
        _event("Non-binary social", "community", ["community"]),
        _event("Intersex awareness workshop", "community", ["community"]),
        _event("Asexual and aromantic meetup", "community", ["community"]),
        _event("Genderfluid support group", "community", ["community"]),
        _event("Sapphic film night", "community", ["community"]),
    ]

    lgbtq = _summaries("pride", events)
    monthly = _summaries("monthly", events)

    assert {event["summary"] for event in events}.issubset(lgbtq)
    assert not ({event["summary"] for event in events} & monthly)



def test_furry_events_are_routed_to_kink_calendar_not_monthly_or_lgbtq_calendar():
    event = _event("Furry community furmeet", "community", ["community", "kink"])

    assert "Furry community furmeet" not in _summaries("monthly", [event])
    assert "Furry community furmeet" not in _summaries("pride", [event])
    assert "Furry community furmeet" in _summaries("kink", [event])







def test_lgbtq_single_and_multi_day_events_preserve_original_spans():
    events = [
        {
            "summary": "Single-day queer meetup",
            "start": date(2027, 6, 12),
            "end": date(2027, 6, 13),
            "description": "Single day",
            "category": "community",
            "categories": ["lgbtq"],
            "location": "",
        },
        {
            "summary": "Multi-day Pride festival",
            "start": date(2027, 6, 14),
            "end": date(2027, 6, 18),
            "description": "Multi day",
            "category": "community",
            "categories": ["lgbtq"],
            "location": "",
        },
    ]
    calendar = ChastityChallengeCalendar(
        SimpleNamespace(data=events), "pride", "test-entry"
    )
    results = {
        event.summary: event
        for event in calendar._events_between(date(2027, 6, 1), date(2027, 7, 1))
        if event.summary in {"Single-day queer meetup", "Multi-day Pride festival"}
    }

    assert results["Single-day queer meetup"].start == date(2027, 6, 12)
    assert results["Single-day queer meetup"].end == date(2027, 6, 13)
    assert results["Multi-day Pride festival"].start == date(2027, 6, 14)
    assert results["Multi-day Pride festival"].end == date(2027, 6, 18)




