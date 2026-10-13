"""Regression tests for concise event sensor state names."""

from custom_components.chastity_calendar.sensor import _sensor_event_name


def test_sensor_event_name_strips_ticketing_and_schedule_suffix():
    assert _sensor_event_name(
        "Queering North East History: Archiving Ourselves Tickets, "
        "Monday, October 26 • 6 PM - 8 PM"
    ) == "Queering North East History: Archiving Ourselves"


def test_sensor_event_name_strips_ticket_suffix_case_insensitively():
    assert _sensor_event_name("Pride social TICKET, details here") == "Pride social"
    assert _sensor_event_name("Pride social tickets, details here") == "Pride social"


def test_sensor_event_name_preserves_names_without_ticket_suffix():
    assert _sensor_event_name("Pride Festival") == "Pride Festival"
    assert _sensor_event_name("Tickets to the Future") == "Tickets to the Future"


def test_sensor_event_name_handles_empty_or_missing_summary_values():
    assert _sensor_event_name("") == ""
    assert _sensor_event_name(None) == ""
