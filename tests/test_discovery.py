"""Regression tests for event-discovery helpers."""
from datetime import datetime

from custom_components.chastity_calendar.discovery import (
    _add_months,
    _category_tags,
    _deduplicate,
    _is_sauna_event,
    _is_target_event,
    _normalise_url,
    _find_future_date,
    _gaysaunas_venue_urls,
    _iter_jsonld_events,
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



def test_target_event_filter_rejects_unrelated_comedy_listing():
    event = _event(
        "North Shields Comedy Club: NEW ACT OF THE YEAR Tickets",
        datetime(2026, 10, 18),
        url="https://example.test/comedy",
    )
    event["description"] = "Stand-up comedy competition at a local venue."

    assert not _is_target_event(event)


def test_target_event_filter_keeps_supported_event_topics():
    start = datetime(2027, 6, 12)
    cases = [
        _event("Newcastle Pride Festival", start),
        _event("Gay Sauna Theme Night", start),
        _event("Queer BDSM Social", start),
        _event("Leather and Fetish Market", start),
        _event("Non-binary Community Meetup", start),
        _event("Pansexual and Bisexual Social", start),
        _event("Intersex Awareness Workshop", start),
        _event("Asexual and Aromantic Meetup", start),
        _event("Transmasc and Genderfluid Support Group", start),
        _event("Two-Spirit Community Gathering", start),
        _event("Queer Film Night", start),
        _event("Shibari and Rope Workshop", start),
        _event("Pup Play Social", start),
        _event("Furry Convention and Furmeet", start),
    ]

    assert all(_is_target_event(event) for event in cases)

def test_event_datetime_extracts_am_pm_time_from_listing_title():
    from custom_components.chastity_calendar.discovery import _find_event_datetime

    result = _find_event_datetime(
        "Fri 16th Oct '26 6:00pm Abfurtay - Furry Student Society",
        datetime(2026, 10, 14),
    )
    assert result == datetime(2026, 10, 16, 18, 0)


def test_event_datetime_extracts_24_hour_time():
    from custom_components.chastity_calendar.discovery import _find_event_datetime

    result = _find_event_datetime(
        "Community event 16 October 2026 18:30",
        datetime(2026, 10, 14),
    )
    assert result == datetime(2026, 10, 16, 18, 30)


def test_timed_record_uses_short_default_duration_instead_of_all_day_span():
    event = _record(
        "Ab-Fur-Tay", datetime(2026, 10, 16, 18, 0),
        "https://example.test/event", "kink", "Furry society meeting",
    )
    assert event["start"] == datetime(2026, 10, 16, 18, 0)
    assert event["end"] == datetime(2026, 10, 16, 20, 0)


def test_future_date_accepts_month_day_without_year():
    result = _find_future_date("Pride social on Friday 16 October", datetime(2026, 10, 13))
    assert result == datetime(2026, 10, 16)


def test_future_date_accepts_abbreviated_month_without_year():
    result = _find_future_date("Queer meetup: Nov 7", datetime(2026, 10, 13))
    assert result == datetime(2026, 11, 7)


def test_yearless_date_keeps_recent_past_event_in_history_window():
    result = _find_future_date("Gay film night on 3 October", datetime(2026, 10, 13))
    assert result == datetime(2026, 10, 3)


def test_future_date_accepts_uk_numeric_date():
    result = _find_future_date("Pride event 17/10/2026", datetime(2026, 10, 13))
    assert result == datetime(2026, 10, 17)


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


def test_normalise_url_removes_tracking_parameters_and_trailing_slash():
    assert _normalise_url(
        "HTTPS://Example.Test/events/pride/?utm_source=newsletter&fbclid=abc"
    ) == "https://example.test/events/pride"


def test_furryguides_quick_facts_time_range_extracts_start_time():
    from custom_components.chastity_calendar.discovery import _event_page_start_time

    body = """
    <ul class="quick-facts">
      <li><span>Date</span><span>October 17, 2026</span></li>
      <li><span>Location</span><span>Birmingham</span></li>
      <li><span>Time</span><span>12 PM - 6 PM</span></li>
    </ul>
    """
    assert _event_page_start_time(body).strftime("%H:%M") == "12:00"


def test_furdar_event_page_time_field_extracts_24_hour_start_time():
    from custom_components.chastity_calendar.discovery import _event_page_start_time

    body = "<div>Event date: 31 October 2026</div><div>Time: 18:00 - 23:00</div>"
    assert _event_page_start_time(body).strftime("%H:%M") == "18:00"


def test_furryguides_quick_facts_time_range_accepts_colon_and_minutes():
    from custom_components.chastity_calendar.discovery import _furryguides_time_range

    assert _event_page_start_time("<b>Time:</b> 12:30 p.m. – 6:00 p.m.") is not None
    assert _event_page_start_time("<b>Time:</b> 12:30 p.m. – 6:00 p.m.").strftime("%H:%M") == "12:30"


def test_find_future_date_prefers_earliest_explicit_future_date():
    today = datetime(2026, 10, 13)
    assert _find_future_date(
        "Festival dates: June 12, 2027 and December 1, 2026", today
    ) == datetime(2026, 12, 1)


def test_find_future_date_ignores_dates_outside_supported_window():
    today = datetime(2026, 10, 13)
    assert _find_future_date("Event on January 1, 2030", today) is None


def test_kink_event_searches_cover_major_fetish_communities():
    from custom_components.chastity_calendar.discovery import SEARCHES

    query_text = " ".join(query.casefold() for _category, query in SEARCHES)
    for term in ("leather", "latex", "shibari", "pup play", "foot fetish", "findom", "furry", "furmeet"):
        assert term in query_text


def test_kink_category_tags_cover_major_fetish_interests():
    tags = set()
    for title in (
        "Leather Weekend", "Rubber and latex social", "Shibari rope workshop",
        "Pup play meetup", "Foot fetish night", "Findom community event", "Furry social",
    ):
        tags.update(_category_tags("community", title, ""))
    assert "kink" in tags


def test_discovery_searches_cover_straight_gay_lesbian_and_other_kink_communities():
    from custom_components.chastity_calendar.discovery import SEARCHES

    queries = " ".join(query.casefold() for _category, query in SEARCHES)
    for term in (
        "straight kink", "gay bdsm", "lesbian kink", "sapphic kink",
        "bisexual kink", "trans kink", "queer kink", "couples bdsm",
        "dominatrix", "crossdressing", "impact play", "sensory deprivation",
        "site:othernights.com/e/", "site:kinkready.com/events", "site:londonalternativemarket.com",
        "site:regulation.co.uk/pages/uk-fetish-calendar", "site:fetish.events/gb",
        "site:thefetishnetwork.com/events",
    ):
        assert term in queries


def test_record_preserves_structured_event_page_date_confidence():
    from custom_components.chastity_calendar.discovery import _record

    event = _record(
        "Rubber social",
        datetime(2026, 11, 13),
        "https://example.test/event",
        "kink",
        "Date verified from event-page metadata.",
        date_confidence="extracted_from_event_page",
    )

    assert event["date_confidence"] == "extracted_from_event_page"
    assert event["source_links"] == ["https://example.test/event"]


def test_date_extraction_keeps_recent_past_events_for_calendar_history():
    today = datetime(2026, 10, 14)
    assert _find_future_date("Queer film night on October 1, 2026", today) == datetime(2026, 10, 1)
    assert _find_future_date("Sauna social on 1 April 2026", today) is None


def test_date_extraction_keeps_recent_past_date_without_year():
    today = datetime(2026, 10, 14)
    assert _find_future_date("Pride event on 1 October", today) == datetime(2026, 10, 1)


def test_gaysaunas_directory_extracts_individual_venue_pages_only():
    html = """
    <a href="/uk/england/">England</a>
    <a href="/uk/england/north-east/">North East</a>
    <a href="/uk/england/north-east/number-52-sauna-newcastle/">Number 52</a>
    <a href="https://gaysaunas.co.uk/uk/england/london/sweatbox-soho/?utm_source=test">Sweatbox</a>
    <a href="https://example.com/uk/england/london/other-venue/">External</a>
    <a href="/uk/england/north-east/number-52-sauna-newcastle/">Duplicate</a>
    """
    assert _gaysaunas_venue_urls(html) == [
        "https://gaysaunas.co.uk/uk/england/north-east/number-52-sauna-newcastle/",
        "https://gaysaunas.co.uk/uk/england/london/sweatbox-soho/",
    ]


def test_gaysaunas_directory_reads_explicit_jsonld_event_dates():
    body = '''
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Event",
      "name": "Fetish Night",
      "startDate": "2026-11-05T18:00:00",
      "url": "https://gaysaunas.co.uk/uk/england/north-east/number-52-sauna-newcastle/"
    }
    </script>
    '''
    events = list(_iter_jsonld_events(body))
    assert len(events) == 1
    assert events[0]["name"] == "Fetish Night"
    assert events[0]["startDate"] == "2026-11-05T18:00:00"


def test_gaysaunas_directory_ignores_non_event_jsonld():
    body = '''
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "LocalBusiness", "name": "Sauna"}
    </script>
    '''
    assert list(_iter_jsonld_events(body)) == []


def test_deduplicate_merges_near_identical_titles_on_same_day():
    start = datetime(2027, 6, 12)
    first = _event("Newcastle Pride Festival", start, source="RSS A")
    second = _event("Newcastle Pride Festival 2027", start, source="Ticketmaster")

    result = _deduplicate([first, second])

    assert len(result) == 1
    assert set(result[0]["sources"]) == {"RSS A", "Ticketmaster"}


def test_deduplicate_keeps_distinct_events_on_the_same_day():
    start = datetime(2027, 6, 12)
    events = [
        _event("Fetish Night", start),
        _event("Sports Night", start),
        _event("Pride Festival", start),
    ]

    result = _deduplicate(events)

    assert len(result) == 3



def test_deduplicate_merges_cross_source_same_event_and_keeps_source_links():
    start = datetime(2027, 6, 12)
    first = _event("Newcastle Pride Festival", start, source="RSS A", url="https://a.test/pride")
    second = _event("Newcastle Pride Festival", start, source="RSS B", url="https://b.test/pride")
    first["location"] = "Newcastle"
    second["location"] = "Newcastle, UK"

    result = _deduplicate([first, second])

    assert len(result) == 1
    assert set(result[0]["sources"]) == {"RSS A", "RSS B"}
    assert set(result[0]["source_links"]) == {"https://a.test/pride", "https://b.test/pride"}


def test_deduplicate_does_not_merge_same_title_and_date_at_different_venues():
    start = datetime(2027, 6, 12)
    first = _event("Pride Social", start, url="https://a.test/pride")
    second = _event("Pride Social", start, url="https://b.test/pride")
    first["location"] = "Newcastle Civic Centre"
    second["location"] = "Gateshead Town Hall"

    result = _deduplicate([first, second])

    assert len(result) == 2


def test_deduplicate_preserves_longer_multi_day_span():
    from datetime import timedelta

    start = datetime(2027, 6, 12)
    short = _event("Queer Community Festival", start, source="RSS A")
    long = _event("Queer Community Festival", start, source="RSS B")
    short["end"] = start + timedelta(days=1)
    long["end"] = start + timedelta(days=3)

    result = _deduplicate([short, long])

    assert len(result) == 1
    assert result[0]["end"] == start + timedelta(days=3)



def test_find_future_date_parses_compact_furryguides_listing_dates():
    today = datetime(2026, 10, 15)

    assert _find_future_date("OCT172026 Birmingham Furs", today) == datetime(2026, 10, 17)
    assert _find_future_date("SEP262027 Cambridge Furs", today) == datetime(2027, 9, 26)


def test_find_future_date_parses_furryguides_multi_day_convention_ranges():
    today = datetime(2026, 10, 15)

    assert _find_future_date("NOV 20 2026 Furcation Brean", today) == datetime(2026, 11, 20)
    assert _find_future_date("Pawsome October 1 – 5, 2026 Gloucester", today) == datetime(2026, 10, 1)



def test_furry_event_title_prefers_visible_event_heading():
    from custom_components.chastity_calendar.discovery import _event_page_title

    body = """
    <html><head><title>Events | FurDar</title></head>
    <body><h1>BCP Furries: Furmeets in Bournemouth &amp; Christchurch</h1></body></html>
    """
    assert _event_page_title(body) == "BCP Furries: Furmeets in Bournemouth & Christchurch"


def test_furry_event_title_reads_open_graph_metadata_when_no_heading():
    from custom_components.chastity_calendar.discovery import _event_page_title

    body = '<meta content="BCP Furries: Furmeets in Bournemouth" property="og:title">'
    assert _event_page_title(body) == "BCP Furries: Furmeets in Bournemouth"


def test_furry_event_title_falls_back_to_html_title():
    from custom_components.chastity_calendar.discovery import _event_page_title

    assert _event_page_title("<title>BCP Furries - FurDar</title>") == "BCP Furries - FurDar"
