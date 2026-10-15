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


def test_overlapping_event_is_assigned_to_only_one_focused_calendar():
    event = _event("Queer sauna social", "sauna", ["sauna", "queer", "lgbtq"])

    assert "Queer sauna social" not in _summaries("monthly", [event])
    assert "Queer sauna social" not in _summaries("pride", [event])
    assert "Queer sauna social" not in _summaries("kink", [event])
    assert "Queer sauna social" in _summaries("sauna", [event])


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
    assert "Queer Film Night" not in _summaries("sauna", [event])



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



def test_timed_discovered_events_are_timezone_aware():
    """Naive source datetimes must not make Home Assistant reject CalendarEvent."""
    event = _event("Sauna session", "sauna", ["sauna"])
    sauna = ChastityChallengeCalendar(SimpleNamespace(data=[event]), "sauna", "test-entry")
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
    sauna = ChastityChallengeCalendar(SimpleNamespace(data=events), "sauna", "test-entry")
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
    sauna = ChastityChallengeCalendar(SimpleNamespace(data=[event]), "sauna", "test-entry")
    result = sauna._events_between(date(2027, 6, 1), date(2027, 7, 1))

    assert len(result) == 1
    assert result[0].start.tzinfo is not None
    assert result[0].start.utcoffset() is not None
    assert result[0].end.tzinfo is not None
    assert result[0].end.utcoffset() is not None



def test_verified_crown_days_appear_only_on_monthly_calendar():
    coordinator = SimpleNamespace(data=[], crown_days={"2027-06-12"})
    monthly = ChastityChallengeCalendar(coordinator, "monthly", "test-entry")
    monthly_events = monthly._events_between(date(2027, 6, 1), date(2027, 7, 1))
    crowns = [event for event in monthly_events if "participation crown" in event.summary]

    assert len(crowns) == 1
    assert crowns[0].summary == "👑 Summer Chastity Challenge participation crown"
    assert crowns[0].start == date(2027, 6, 12)
    assert crowns[0].end == date(2027, 6, 13)

    sauna = ChastityChallengeCalendar(coordinator, "sauna", "test-entry")
    sauna_events = sauna._events_between(date(2027, 6, 1), date(2027, 7, 1))
    assert not any("participation crown" in event.summary for event in sauna_events)


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



def test_gay_sauna_events_appear_in_both_sauna_and_lgbtq_calendars():
    event = _event(
        "Fetish Night at Number 52 Sauna",
        "sauna",
        ["sauna", "gay", "lgbtq", "kink"],
    )
    event["source"] = "Number 52 Sauna official website"
    event["url"] = "https://www.number52sauna.co.uk/our-events/"

    assert "Fetish Night at Number 52 Sauna" not in _summaries("monthly", [event])
    assert "Fetish Night at Number 52 Sauna" in _summaries("sauna", [event])
    assert "Fetish Night at Number 52 Sauna" in _summaries("pride", [event])
    assert "Fetish Night at Number 52 Sauna" not in _summaries("kink", [event])


def test_non_gay_sauna_events_remain_out_of_lgbtq_calendar():
    event = _event("General Sauna Session", "sauna", ["sauna"])
    event["source"] = "Generic sauna listing"
    event["url"] = "https://example.com/sauna/events"

    assert "General Sauna Session" in _summaries("sauna", [event])
    assert "General Sauna Session" not in _summaries("pride", [event])


def test_midnight_date_only_discovery_renders_as_all_day():
    """A date-only source timestamp must not appear as a midnight timed event."""
    event = {
        "summary": "Date-only sauna event",
        "start": datetime(2027, 6, 14),
        "end": datetime(2027, 6, 15),
        "description": "All day",
        "category": "sauna",
        "categories": ["sauna"],
        "location": "",
        "all_day": True,
    }
    sauna = ChastityChallengeCalendar(SimpleNamespace(data=[event]), "sauna", "test-entry")
    result = sauna._events_between(date(2027, 6, 1), date(2027, 7, 1))

    assert len(result) == 1
    assert type(result[0].start) is date
    assert type(result[0].end) is date
    assert result[0].start == date(2027, 6, 14)
    assert result[0].end == date(2027, 6, 15)
