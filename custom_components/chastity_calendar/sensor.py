"""Upcoming-event sensors for Chastity Challenge Calendar."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util

from .calendar import ChastityChallengeCalendar
from .const import DOMAIN


COUNT_WINDOW_DAYS = 30


class ChastityCalendarSensorBase(SensorEntity):
    """Base class for sensors backed by the shared event coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator) -> None:
        """Initialize the sensor and retain the shared discovery coordinator."""
        self.coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Refresh sensor state whenever discovered events are updated."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    def _events_between(self, start_day: date, end_day: date):
        """Return built-in and discovered events from both calendars."""
        monthly = ChastityChallengeCalendar(self.coordinator, "monthly")
        pride = ChastityChallengeCalendar(self.coordinator, "pride")
        events = (
            monthly._events_between(start_day, end_day)
            + pride._events_between(start_day, end_day)
        )
        # Avoid duplicate entries if an online result overlaps a built-in entry.
        unique = {}
        for event in events:
            key = (
                event.summary,
                event.start_datetime_local.date(),
                event.end_datetime_local.date(),
            )
            unique[key] = event
        return sorted(unique.values(), key=lambda event: event.start_datetime_local)


class ChastityNextEventSensor(ChastityCalendarSensorBase):
    """Expose the name and date of the next current/upcoming event."""

    _attr_name = "Next Event"
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator) -> None:
        """Initialize the next-event sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_next_event"

    @property
    def native_value(self) -> str | None:
        """Return the next event's summary, or None if no event is available."""
        event = self._next_event()
        return event.summary if event else None

    @property
    def extra_state_attributes(self) -> dict:
        """Expose useful event details for dashboards and automations."""
        event = self._next_event()
        if event is None:
            return {}
        return {
            "start_date": event.start_datetime_local.date().isoformat(),
            "end_date": (
                event.end_datetime_local.date() - timedelta(days=1)
            ).isoformat(),
            "description": event.description,
        }

    def _next_event(self):
        """Find the first event that has not yet ended."""
        now = dt_util.now()
        today = now.date()
        events = self._events_between(today, date(today.year + 2, 1, 1))
        return next(
            (event for event in events if event.end_datetime_local > now),
            None,
        )


class ChastityUpcomingEventCountSensor(ChastityCalendarSensorBase):
    """Count current/upcoming events over the next 30 days."""

    _attr_name = "Upcoming Events"
    _attr_icon = "mdi:calendar-multiple"

    def __init__(self, coordinator) -> None:
        """Initialize the upcoming-event count sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_upcoming_event_count"

    @property
    def native_value(self) -> int:
        """Return the number of events overlapping the next 30 days."""
        now = dt_util.now()
        today = now.date()
        horizon = now + timedelta(days=COUNT_WINDOW_DAYS)
        events = self._events_between(today, horizon.date() + timedelta(days=1))
        return sum(
            1
            for event in events
            if event.end_datetime_local > now
            and event.start_datetime_local < horizon
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Describe the counting window."""
        return {
            "window_days": COUNT_WINDOW_DAYS,
            "window_description": "Current and upcoming events over the next 30 days",
        }


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the next-event and upcoming-event-count sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ChastityNextEventSensor(coordinator),
            ChastityUpcomingEventCountSensor(coordinator),
        ]
    )
