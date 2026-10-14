"""Focused event sensors and the nearest-sauna venue sensor."""
from __future__ import annotations

from datetime import date, timedelta
import re
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_change

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util

from .calendar import ChastityChallengeCalendar
from .const import DOMAIN


def _sensor_event_name(summary: str) -> str:
    """Strip ticketing/date/time text appended by event-listing sources.

    The original summary remains untouched in the calendar entity; this helper
    only shortens the event name displayed as a sensor state.
    """
    return re.sub(r"\s+Tickets?\s*(?:,|:|[-–—•]).*$", "", str(summary or ""), flags=re.IGNORECASE).strip()


class ChastityCalendarSensorBase(SensorEntity):
    """Base class for sensors backed by the shared event coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str) -> None:
        self.coordinator = coordinator
        self.entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{self._attr_name.lower().replace(' ', '_')}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Chastity Events",
            manufacturer="Chastity Events",
            configuration_url="https://github.com/jonny5509/Chastity-Events",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        # These sensors derive their values from the current date and shared
        # discovery data. Re-evaluate on the same cadence as discovery so
        # events that start/end or roll past midnight are reflected promptly.
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._scheduled_state_refresh,
                hour=[0, 6, 12, 18], minute=0, second=0,
            )
        )

    def _handle_coordinator_update(self) -> None:
        """Refresh sensor state when discovery data changes."""
        self.async_write_ha_state()

    async def _scheduled_state_refresh(self, _now) -> None:
        """Refresh sensor state when the event window changes."""
        self._handle_coordinator_update()

    def _events(self, calendar_type: str, start_day: date, end_day: date):
        calendar = ChastityChallengeCalendar(self.coordinator, calendar_type, self.entry_id)
        return calendar._events_between(start_day, end_day)


class ChastityCalendarStatusSensor(ChastityCalendarSensorBase):
    """Mirror whether a calendar currently has an active event."""

    calendar_type = ""
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        # Preserve the original registry IDs while making the display names
        # distinct from their same-named calendar entities.
        self._attr_unique_id = (
            f"{DOMAIN}_{entry_id}_{self._legacy_entity_name.lower().replace(' ', '_')}"
        )

    @property
    def native_value(self) -> str:
        """Report On while an event is in progress, otherwise Off."""
        now = dt_util.now()
        today = now.date()
        events = self._events(self.calendar_type, today, today + timedelta(days=2))
        active = any(
            event.start_datetime_local <= now < event.end_datetime_local
            for event in events
        )
        return "On" if active else "Off"

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the matching calendar entity and active event, if any."""
        now = dt_util.now()
        today = now.date()
        events = self._events(self.calendar_type, today, today + timedelta(days=2))
        active = next(
            (event for event in events
             if event.start_datetime_local <= now < event.end_datetime_local),
            None,
        )
        calendar_entities = {
            "monthly": "calendar.monthly_events",
            "pride": "calendar.lgbtq_events",
            "sauna": "calendar.sauna_events",
            "kink": "calendar.kink_fetish_events",
        }
        return {
            "calendar_entity": calendar_entities[self.calendar_type],
            "active_event": active.summary if active else None,
        }


class ChastityMonthlyEventsStatusSensor(ChastityCalendarStatusSensor):
    """Status of the Monthly Events calendar."""

    calendar_type = "monthly"
    _legacy_entity_name = "Monthly Events"
    _attr_name = "Monthly Events Status"
    _attr_icon = "mdi:calendar-heart"


class ChastityLGBTQEventsStatusSensor(ChastityCalendarStatusSensor):
    """Status of the LGBTQ+ Events calendar."""

    calendar_type = "pride"
    _legacy_entity_name = "LGBTQ+ Events"
    _attr_name = "LGBTQ+ Events Status"
    _attr_icon = "mdi:flag"


class ChastitySaunaEventsStatusSensor(ChastityCalendarStatusSensor):
    """Status of the Sauna Events calendar."""

    calendar_type = "sauna"
    _legacy_entity_name = "Sauna Events"
    _attr_name = "Sauna Events Status"
    _attr_icon = "mdi:hot-tub"


class ChastityKinkEventsStatusSensor(ChastityCalendarStatusSensor):
    """Status of the Kink & Fetish Events calendar."""

    calendar_type = "kink"
    _legacy_entity_name = "Kink & Fetish Events"
    _attr_name = "Kink & Fetish Events Status"
    _attr_icon = "mdi:calendar-heart"


class ChastityOngoingMonthEventSensor(ChastityCalendarSensorBase):
    """Show a monthly challenge event that is active today."""

    _attr_name = "Ongoing Month Event"
    _attr_icon = "mdi:calendar-heart"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)

    def _event(self):
        today = dt_util.now().date()
        return next(iter(self._events("monthly", today, today + timedelta(days=1))), None)

    @property
    def native_value(self) -> str:
        event = self._event()
        return _sensor_event_name(event.summary) if event else "No ongoing month event"

    @property
    def extra_state_attributes(self) -> dict:
        """Keep event details in the calendar, not duplicated on the sensor."""
        return {}


class ChastityNextMonthEventSensor(ChastityCalendarSensorBase):
    """Show the first event starting in the next calendar month."""

    _attr_name = "Next Month Event"
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)

    def _event(self):
        today = dt_util.now().date()
        next_month_start = date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1)
        following_month = date(next_month_start.year + (next_month_start.month == 12), 1 if next_month_start.month == 12 else next_month_start.month + 1, 1)
        events = self._events("monthly", next_month_start, following_month)
        return events[0] if events else None

    @property
    def native_value(self) -> str:
        event = self._event()
        return _sensor_event_name(event.summary) if event else "No event next month"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return {}


class ChastityPastLGBTQEventSensor(ChastityCalendarSensorBase):
    """Show the most recent LGBTQ+ event that has ended."""

    _attr_name = "Past LGBTQ Event"
    _attr_icon = "mdi:flag"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)

    def _event(self):
        today = dt_util.now().date()
        events = self._events("pride", date(today.year - 2, 1, 1), today + timedelta(days=1))
        past = [event for event in events if event.end_datetime_local.date() <= today]
        return max(past, key=lambda event: event.end_datetime_local) if past else None

    @property
    def native_value(self) -> str:
        event = self._event()
        return _sensor_event_name(event.summary) if event else "No past LGBTQ event"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return {}


class ChastityNextLGBTQEventSensor(ChastityCalendarSensorBase):
    """Show the next ongoing or upcoming LGBTQ+ event."""

    _attr_name = "Next LGBTQ Event"
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)

    def _event(self):
        today = dt_util.now().date()
        events = self._events("pride", today, date(today.year + 2, 1, 1))
        upcoming = [event for event in events if event.end_datetime_local.date() > today]
        return min(upcoming, key=lambda event: event.start_datetime_local) if upcoming else None

    @property
    def native_value(self) -> str:
        event = self._event()
        return _sensor_event_name(event.summary) if event else "No upcoming LGBTQ event"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return {}


class ChastityNextCategoryEventSensor(ChastityCalendarSensorBase):
    """Show the next discovered event for a specific LGBTQ+ category."""

    category = ""
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)

    def _event(self):
        today = dt_util.now().date()
        events = self._events("pride", today, date(today.year + 2, 1, 1))

        # Match the event's own title/description, not just the search query's
        # category tag. Search-source tags can label a generic result as "gay"
        # or "lesbian", which made every sensor select the same event.
        category_terms = {
            "gay": ("gay", "harvey milk", "gay men"),
            "lesbian": ("lesbian", "sapphic"),
            "bisexual": ("bisexual", "bi visibility", "bi pride"),
            "transgender": (
                "transgender", "trans day of visibility",
                "transgender day of visibility", "trans day of remembrance",
                "transgender day of remembrance", "trans pride",
            ),
            "queer": ("queer",),
        }
        terms = category_terms.get(self.category, (self.category,))
        matching_summaries = set()
        for item in self.coordinator.data or []:
            # The discovery query/category is useful evidence for category-
            # specific sensors: event titles may omit words such as "gay"
            # even when returned by the gay-events search.
            item_categories = {
                str(value).casefold() for value in item.get("categories", [])
            }
            item_category = str(item.get("category", "")).casefold()
            text = " ".join((
                str(item.get("summary", "")),
                str(item.get("description", "")),
                item_category,
                " ".join(item_categories),
            )).casefold()
            if item_category == self.category or self.category in item_categories or any(
                term in text for term in terms
            ):
                matching_summaries.add(item.get("summary", ""))

        upcoming = [
            event for event in events
            if event.end_datetime_local.date() > today
            and (
                event.summary in matching_summaries
                or any(term in f"{event.summary} {event.description or ''}".casefold()
                       for term in terms)
            )
        ]
        return min(upcoming, key=lambda event: event.start_datetime_local) if upcoming else None

    @property
    def native_value(self) -> str:
        event = self._event()
        return _sensor_event_name(event.summary) if event else f"No upcoming {self.category.title()} event"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return {}


class ChastityNextGayEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered gay event."""

    category = "gay"
    _attr_name = "Next Gay Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextLesbianEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered lesbian event."""

    category = "lesbian"
    _attr_name = "Next Lesbian Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextBisexualEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered bisexual event."""

    category = "bisexual"
    _attr_name = "Next Bisexual Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextTransgenderEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered transgender event."""

    category = "transgender"
    _attr_name = "Next Transgender Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextQueerEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered queer community event."""

    category = "queer"
    _attr_name = "Next Queer Event"
    _attr_icon = "mdi:account-multiple"



class ChastityNearestSaunaSensor(SensorEntity):
    """Show the nearest sauna mapped in OpenStreetMap to the configured location."""

    _attr_has_entity_name = True
    _attr_name = "Nearest Sauna"
    _attr_icon = "mdi:hot-tub"
    _attr_should_poll = False

    def __init__(self, hass, entry, preferences) -> None:
        self.hass = hass
        self.preferences = preferences
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_nearest_sauna"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Chastity Events",
            manufacturer="Chastity Events",
            configuration_url="https://github.com/jonny5509/Chastity-Events",
        )
        self._saunas = []
        self._unsub_refresh = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_refresh()
        self._unsub_refresh = async_track_time_change(
            self.hass, self._scheduled_refresh, hour=[0, 6, 12, 18], minute=0, second=0
        )
        self.async_on_remove(self._unsub_refresh)

    async def _scheduled_refresh(self, _now) -> None:
        await self._async_refresh()

    async def _async_refresh(self) -> None:
        from .discovery import async_discover_nearest_saunas
        self._saunas = await async_discover_nearest_saunas(
            self.hass,
            country=self.preferences.get("country", ""),
            location=", ".join(filter(None, (
                self.preferences.get("area", ""),
                self.preferences.get("city", ""),
                self.preferences.get("county", ""),
                self.preferences.get("region", ""),
                self.preferences.get("location", ""),
            ))),
        )
        self.async_write_ha_state()

    @property
    def native_value(self):
        if not self._saunas:
            return "No mapped sauna found"
        return self._saunas[0]["name"]

    @property
    def extra_state_attributes(self) -> dict:
        if not self._saunas:
            return {"search_radius_km": 30, "data_source": "OpenStreetMap"}
        nearest = self._saunas[0]
        return {
            "distance_km": nearest["distance_km"],
            "address": nearest["address"],
            "website": nearest["website"],
            "phone": nearest["phone"],
            "latitude": nearest["latitude"],
            "longitude": nearest["longitude"],
            "map_url": nearest["osm_url"],
            "search_radius_km": 30,
            "other_nearby_saunas": self._saunas[1:6],
            "data_source": "OpenStreetMap",
        }



class ChastityNextSaunaEventSensor(ChastityCalendarSensorBase):
    """Show the next discovered public sauna event."""

    _attr_name = "Next Sauna Event"
    _attr_icon = "mdi:calendar-star"

    def _event_record(self):
        today = dt_util.now().date()
        matches = []
        for item in self.coordinator.data or []:
            searchable = " ".join(str(item.get(key, "")) for key in (
                "summary", "description", "category", "location"
            )) + " " + " ".join(str(value) for value in item.get("categories", []))
            if "sauna" not in searchable.casefold():
                continue
            start = item.get("start")
            if not start:
                continue
            if hasattr(start, "date"):
                event_date = start.date()
            else:
                try:
                    event_date = date.fromisoformat(str(start)[:10])
                except ValueError:
                    continue
            if event_date >= today:
                matches.append((event_date, item))
        return min(matches, key=lambda match: match[0])[1] if matches else None

    @property
    def native_value(self) -> str:
        event = self._event_record()
        if not event:
            return "No upcoming sauna event found"
        start = event.get("start")
        event_date = start.date().isoformat() if hasattr(start, "date") else str(start)[:10]
        return _sensor_event_name(event.get("summary", "Sauna event"))

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event_record()
        if not event:
            return {}
        start = event.get("start")
        event_date = start.date().isoformat() if hasattr(start, "date") else str(start)[:10]
        # Detailed event metadata belongs to the Sauna Events calendar.
        return {}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up focused monthly, LGBTQ+, and category-specific event sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    preferences = {**entry.data, **entry.options}
    async_add_entities([
        ChastityMonthlyEventsStatusSensor(coordinator, entry.entry_id),
        ChastityLGBTQEventsStatusSensor(coordinator, entry.entry_id),
        ChastitySaunaEventsStatusSensor(coordinator, entry.entry_id),
        ChastityKinkEventsStatusSensor(coordinator, entry.entry_id),
        ChastityNearestSaunaSensor(hass, entry, preferences),
        ChastityNextSaunaEventSensor(coordinator, entry.entry_id),
        ChastityOngoingMonthEventSensor(coordinator, entry.entry_id),
        ChastityNextMonthEventSensor(coordinator, entry.entry_id),
        ChastityPastLGBTQEventSensor(coordinator, entry.entry_id),
        ChastityNextLGBTQEventSensor(coordinator, entry.entry_id),
        ChastityNextGayEventSensor(coordinator, entry.entry_id),
        ChastityNextLesbianEventSensor(coordinator, entry.entry_id),
        ChastityNextBisexualEventSensor(coordinator, entry.entry_id),
        ChastityNextTransgenderEventSensor(coordinator, entry.entry_id),
        ChastityNextQueerEventSensor(coordinator, entry.entry_id),
    ])
