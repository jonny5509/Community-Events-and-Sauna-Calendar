"""Regression tests for event-discovery helpers."""
from datetime import datetime

from custom_components.chastity_calendar.discovery import (
    _add_months,
    _category_tags,
    _deduplicate,
    _is_sauna_event,
    _record,
)


def _event(summary, start, *, source="source A", url="https://example.test/events"):
    return {
        "summary": summary,
        "start": start,
        "end": start,
        "description": "",
        "url": url,
        "category": "community",
        "categories": ["community"],
        "location": "",
        "source": source,
        "sources": [source],
        "source_links": [url],
        "date_confidence": "extracted_from_search_snippet",
    }


def test_deduplicate_merges_same_title_and_date_and_preserves_sources():
    start = datetime(2027, 6, 12)
    first = _event("Pride Festival", start, source="RSS A")
    second = _event("Pride Festival", start, source="Ticketmaster")
    second["categories"] = ["pride", "lgbtq"]

    result = _deduplicate([first, second])

    assert len(result) == 1
    assert result[0]["summary"] == "Pride Festival"
    assert set(result[0]["sources"]) == {"RSS A", "Ticketmaster"}
    assert set(result[0]["categories"]) == {"community", "pride", "lgbtq"}


def test_deduplicate_does_not_collapse_different_events_on_same_page():
    start = datetime(2027, 6, 12)
    first = _event("Fetish Night", start)
    second = _event("Sports Night", start)

    result = _deduplicate([first, second])

    assert {event["summary"] for event in result} == {"Fetish Night", "Sports Night"}


def test_sauna_detection_uses_event_metadata():
    assert _is_sauna_event({"summary": "Theme Night", "category": "sauna"})
    assert _is_sauna_event({"summary": "Number 52 Sauna event"})
    assert not _is_sauna_event({"summary": "Pride Festival", "category": "community"})



def test_generic_theme_night_is_not_misclassified_as_sauna():
    """Generic themed events should not be hidden from the monthly calendar."""
    tags = _category_tags("community", "80s Theme Night", "A themed social event with music.")

    assert "sauna" not in tags


def test_sauna_context_still_classifies_sauna_events():
    """Explicit sauna wording continues to route events to the sauna calendar."""
    tags = _category_tags("community", "Theme Night at Number 52 Sauna", "Steam room event.")

    assert "sauna" in tags



def test_sauna_search_result_without_sauna_context_is_not_routed_to_sauna_calendar():
    """A broad search query alone must not classify generic themed nights."""
    event = _record(
        "80s Theme Night",
        datetime(2027, 6, 12),
        "https://example.test/events/theme-night",
        "sauna",
        "A themed social event with music.",
    )

    assert event["category"] == "community"
    assert "sauna" not in event["categories"]


def test_sauna_search_result_with_explicit_context_is_routed_to_sauna_calendar():
    """Explicit sauna context remains classified as a sauna event."""
    event = _record(
        "Theme Night at Number 52 Sauna",
        datetime(2027, 6, 12),
        "https://www.number52sauna.co.uk/our-events/",
        "sauna",
        "A themed social event.",
    )

    assert event["category"] == "sauna"
    assert "sauna" in event["categories"]

def test_add_months_clamps_end_of_month():
    assert _add_months(datetime(2027, 1, 31), 1) == datetime(2027, 2, 28)
    assert _add_months(datetime(2027, 12, 31), 2) == datetime(2028, 2, 29)
