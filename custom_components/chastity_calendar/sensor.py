"""Four focused sensors for monthly and LGBTQ+ observances."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util

from .calendar import ChastityChallengeCalendar
from .const import DOMAIN


class ChastityCalendarSensorBase(SensorEntity):
    """Base class for sensors backed by the shared event coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{self._attr_name.lower().replace(' ', '_')}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    def _events(self, calendar_type: str, start_day: date, end_day: date):
        calendar = ChastityChallengeCalendar(self.coordinator, calendar_type)
        return calendar._events_between(start_day, end_day)

    @staticmethod
    def _details(event) -> dict:
        return {
            "event": event.summary,
            "start_date": event.start_datetime_local.date().isoformat(),
            "end_date": (event.end_datetime_local.date() - timedelta(days=1)).isoformat(),
            "description": event.description or "",
            "location": getattr(event, "location", "") or "",
        }


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
        return event.summary if event else "No ongoing month event"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return self._details(event) if event else {}


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
        return event.summary if event else "No event next month"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return self._details(event) if event else {}


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
        return event.summary if event else "No past LGBTQ event"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return self._details(event) if event else {}


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
        return event.summary if event else "No upcoming LGBTQ event"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return self._details(event) if event else {}


class ChastityNextCategoryEventSensor(ChastityCalendarSensorBase):
    """Show the next discovered event for a specific LGBTQ+ category."""

    category = ""
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)

    def _event(self):
        today = dt_util.now().date()
        events = self._events("pride", today, date(today.year + 2, 1, 1))
        matching_titles = set()
        for item in self.coordinator.data or []:
            tags = {str(tag).casefold() for tag in item.get("categories", [])}
            category = str(item.get("category", "")).casefold()
            if self.category in tags or category == self.category:
                matching_titles.add(item.get("summary", ""))
        upcoming = [
            event for event in events
            if event.summary in matching_titles and event.end_datetime_local.date() > today
        ]
        return min(upcoming, key=lambda event: event.start_datetime_local) if upcoming else None

    @property
    def native_value(self) -> str:
        event = self._event()
        return event.summary if event else f"No upcoming {self.category.title()} event"

    @property
    def extra_state_attributes(self) -> dict:
        event = self._event()
        return self._details(event) if event else {}


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


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up focused monthly, LGBTQ+, and category-specific event sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
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
