"""Upcoming-event sensors for Chastity Challenge Calendar."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util

from .calendar import ChastityChallengeCalendar
from .const import DOMAIN
from .sauna_sensor import NearbySaunasSensor


COUNT_WINDOW_DAYS = 30
MAX_STATE_LENGTH = 250


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

    def _next_event(self):
        """Find the first event that has not yet ended."""
        now = dt_util.now()
        today = now.date()
        events = self._events_between(today, date(today.year + 2, 1, 1))
        return next(
            (event for event in events if event.end_datetime_local > now),
            None,
        )

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


class ChastityUpcomingEventCountSensor(ChastityCalendarSensorBase):
    """Show upcoming event names and expose their count and dates."""

    _attr_name = "Upcoming Events"
    _attr_icon = "mdi:calendar-multiple"

    def __init__(self, coordinator) -> None:
        """Initialize the upcoming-events sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_upcoming_event_count"

    def _upcoming_events(self):
        """Return events active or starting in the next 30 days."""
        now = dt_util.now()
        today = now.date()
        horizon = now + timedelta(days=COUNT_WINDOW_DAYS)
        events = self._events_between(today, horizon.date() + timedelta(days=1))
        return [
            event
            for event in events
            if event.end_datetime_local > now
            and event.start_datetime_local < horizon
        ]

    @property
    def native_value(self) -> str:
        """Show event names in the sensor state instead of a numeric count."""
        names = list(dict.fromkeys(event.summary for event in self._upcoming_events()))
        if not names:
            return "No upcoming events"
        state = ", ".join(names)
        if len(state) > MAX_STATE_LENGTH:
            state = state[: MAX_STATE_LENGTH - 1].rstrip(", ") + "…"
        return state

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the count and complete list of upcoming event names and dates."""
        events = self._upcoming_events()
        return {
            "count": len(events),
            "window_days": COUNT_WINDOW_DAYS,
            "window_description": "Current and upcoming events over the next 30 days",
            "upcoming_events": [
                {
                    "name": event.summary,
                    "start_date": event.start_datetime_local.date().isoformat(),
                    "end_date": (
                        event.end_datetime_local.date() - timedelta(days=1)
                    ).isoformat(),
                }
                for event in events
            ],
        }


class ChastityEventLocationsSensor(ChastityCalendarSensorBase):
    """Show the configured search area and any explicit event locations."""

    _attr_name = "Event Locations"
    _attr_icon = "mdi:map-marker-multiple"

    def __init__(self, coordinator, country: str, location: str) -> None:
        """Initialize location sensor with the configured search area."""
        super().__init__(coordinator)
        self.country = country.strip()
        self.location = location.strip()
        self._attr_unique_id = f"{DOMAIN}_event_locations"

    @property
    def native_value(self) -> str:
        """Show the configured search area, not an inferred event venue."""
        return ", ".join(part for part in (self.location, self.country) if part) or "Not configured"

    @property
    def extra_state_attributes(self) -> dict:
        """Separate the configured search area from explicitly supplied venues."""
        discovered = self.coordinator.data or []
        event_locations = [
            {
                "name": item.get("summary", "Unnamed event"),
                "location": item["location"],
                "start_date": item["start"].date().isoformat()
                if hasattr(item.get("start"), "date")
                else str(item.get("start", "")),
                "source": item.get("url", ""),
            }
            for item in discovered
            if item.get("location")
        ]
        return {
            "configured_search_area": {
                "city_or_region": self.location or None,
                "country": self.country or None,
            },
            "event_locations": event_locations,
            "event_locations_count": len(event_locations),
            "location_note": (
                "Only explicit event locations are listed here. Current RSS discovery "
                "does not reliably extract venue locations, so this list may be empty. "
                "The configured search area is not proof that an event takes place there."
            ),
        }


class ChastityCategoryEventsSensor(ChastityCalendarSensorBase):
    """Show discovered events matching one LGBTQ+ category."""

    def __init__(self, coordinator, category: str, name: str, icon: str) -> None:
        """Initialize a category-specific event sensor."""
        super().__init__(coordinator)
        self.category = category
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{category}_events"

    def _category_events(self):
        """Return upcoming discovered events tagged with this category."""
        now = dt_util.now()
        discovered = self.coordinator.data or []
        return sorted(
            (
                item for item in discovered
                if item.get("category") == self.category
                and item.get("start") is not None
                and item["start"].date() >= now.date()
            ),
            key=lambda item: item["start"],
        )

    @property
    def native_value(self) -> int:
        """Return the number of matching discovered events."""
        return len(self._category_events())

    @property
    def extra_state_attributes(self) -> dict:
        """Expose matching event names, dates, and source links."""
        events = self._category_events()
        return {
            "count": len(events),
            "category": self.category,
            "events": [
                {
                    "name": item.get("summary", "Unnamed event"),
                    "date": item["start"].date().isoformat(),
                    "source": item.get("url", ""),
                }
                for item in events
            ],
            "note": "Best-effort, unverified public RSS discoveries; this is not a complete event directory.",
        }




async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up event, upcoming-event, and location sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    preferences = {**entry.data, **entry.options}
    async_add_entities(
        [
            NearbySaunasSensor(
                hass,
                preferences.get("country", ""),
                preferences.get("location", ""),
                ", ".join(
                    part for part in (
                        preferences.get("area", ""),
                        preferences.get("city", ""),
                    ) if part and part != "— Skip this level —"
                ) or ", ".join(
                    part for part in (
                        preferences.get("county", ""),
                        preferences.get("region", ""),
                    ) if part and part != "— Skip this level —"
                ),
            ),
            ChastityNextEventSensor(coordinator),
            ChastityUpcomingEventCountSensor(coordinator),
            ChastityEventLocationsSensor(
                coordinator,
                preferences.get("country", ""),
                preferences.get("location", ""),
            ),
            ChastityCategoryEventsSensor(coordinator, "gay", "Gay Events", "mdi:account-group"),
            ChastityCategoryEventsSensor(coordinator, "lesbian", "Lesbian Events", "mdi:account-group"),
            ChastityCategoryEventsSensor(coordinator, "bisexual", "Bisexual Events", "mdi:account-group"),
            ChastityCategoryEventsSensor(coordinator, "transgender", "Transgender Events", "mdi:account-group"),
            ChastityCategoryEventsSensor(coordinator, "queer", "Queer Events", "mdi:account-group"),
            ChastityCategoryEventsSensor(coordinator, "lgbtq", "LGBTQ+ Events", "mdi:calendar-star"),
        ]
    )
