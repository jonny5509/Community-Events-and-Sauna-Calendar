"""Focused event sensors and the nearest-sauna venue sensor."""
from __future__ import annotations

from datetime import date, timedelta
import re
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import dt as dt_util

from .calendar import ChastityChallengeCalendar, _is_gay_sauna_event
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
            name="Community Events & Sauna Calendar",
            manufacturer="Community Events & Sauna Calendar",
            configuration_url="https://github.com/jonny5509/community-events-sauna-calendar",
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

    def _event_attributes(self, event) -> dict:
        """Expose useful details without requiring a separate sensor per category."""
        if event is None:
            return {}
        start = getattr(event, "start", None)
        end = getattr(event, "end", None)
        start_date = start.date() if hasattr(start, "date") else start
        end_date = end.date() if hasattr(end, "date") else end
        summary = str(getattr(event, "summary", "") or "")
        normalized = re.sub(r"[^a-z0-9]+", " ", summary.casefold()).strip()
        record = next((
            item for item in (self.coordinator.data or [])
            if re.sub(r"[^a-z0-9]+", " ", str(item.get("summary", "")).casefold()).strip() == normalized
            and (
                (item.get("start").date() if hasattr(item.get("start"), "date") else item.get("start"))
                == start_date
            )
        ), {})
        sources = record.get("sources") or ([record.get("source")] if record.get("source") else [])
        links = record.get("source_links") or ([record.get("url")] if record.get("url") else [])
        attrs = {
            "event_date": start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date or ""),
            "end_date": end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date or ""),
            "location": record.get("location", ""),
            "source_url": record.get("url", "") or (links[0] if links else ""),
            "sources": sources,
            "source_urls": links,
            "categories": record.get("categories", []),
        }
        return {key: value for key, value in attrs.items() if value not in ("", [], None)}


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
        return self._event_attributes(self._event())



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
        return self._event_attributes(self._event())



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
        return self._event_attributes(self._event())



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
        attrs = self._event_attributes(self._event())
        by_category = {}
        for sensor_class in _CATEGORY_SENSOR_CLASSES:
            candidate = sensor_class(self.coordinator, self.entry_id)._event()
            if candidate:
                details = self._event_attributes(candidate)
                details["name"] = _sensor_event_name(candidate.summary)
                by_category[sensor_class.category] = details
        attrs["next_events_by_category"] = by_category
        return attrs



class ChastityNextCategoryEventSensor(ChastityCalendarSensorBase):
    """Show the next discovered event for a specific LGBTQ+ category."""

    category = ""
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)

    def _event(self):
        today = dt_util.now().date()
        calendar_type = "kink" if self.category == "furry" else "pride"
        events = self._events(calendar_type, today, date(today.year + 2, 1, 1))

        # Match the event's own title/description, not just the search query's
        # category tag. Search-source tags can label a generic result as "gay"
        # or "lesbian", which made every sensor select the same event.
        # Keep category matching in a familiar LGBTQIA+ order. Additional
        # identities and interests follow the core acronym categories.
        category_terms = {
            "lesbian": ("lesbian", "sapphic"),
            "gay": ("gay", "harvey milk", "gay men"),
            "bisexual": ("bisexual", "bi visibility", "bi pride"),
            "transgender": (
                "transgender", "trans day of visibility",
                "transgender day of visibility", "trans day of remembrance",
                "transgender day of remembrance", "trans pride",
            ),
            "queer": ("queer",),
            "intersex": ("intersex",),
            "asexual": ("asexual", "ace community"),
            "pansexual": ("pansexual", "pan pride"),
            "non-binary": ("non-binary", "nonbinary", "enby", "genderqueer"),
            "aromantic": ("aromantic", "aro community"),
            "genderfluid": ("genderfluid",),
            "sapphic": ("sapphic", "wlw", "lesbian"),
            "furry": ("furry", "furmeet", "fursuit"),
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
            # Directory listings can have generic titles (for example
            # "Sauna 52") without explicit LGBTQ+ keywords. The source identifies
            # these as gay-sauna events, so include them in Next Gay.
            is_gay_sauna_for_gay_sensor = (
                self.category == "gay" and _is_gay_sauna_event(item)
            )
            if (
                is_gay_sauna_for_gay_sensor
                or item_category == self.category
                or self.category in item_categories
                or any(term in text for term in terms)
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
        return self._event_attributes(self._event())


class ChastityNextLesbianEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered lesbian event."""

    category = "lesbian"
    _attr_name = "Next Lesbian Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextGayEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered gay event."""

    category = "gay"
    _attr_name = "Next Gay Event"
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


class ChastityNextIntersexEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered intersex community event."""

    category = "intersex"
    _attr_name = "Next Intersex Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextAsexualEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered asexual community event."""

    category = "asexual"
    _attr_name = "Next Asexual Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextPansexualEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered pansexual community event."""

    category = "pansexual"
    _attr_name = "Next Pansexual Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextNonBinaryEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered non-binary community event."""

    category = "non-binary"
    _attr_name = "Next Non-binary Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextAromanticEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered aromantic community event."""

    category = "aromantic"
    _attr_name = "Next Aromantic Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextGenderfluidEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered genderfluid community event."""

    category = "genderfluid"
    _attr_name = "Next Genderfluid Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextSapphicEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered sapphic community event."""

    category = "sapphic"
    _attr_name = "Next Sapphic Event"
    _attr_icon = "mdi:account-multiple"


class ChastityNextFurryEventSensor(ChastityNextCategoryEventSensor):
    """Show the next discovered furry community event."""

    category = "furry"
    _attr_name = "Next Furry Event"
    _attr_icon = "mdi:paw"

_CATEGORY_SENSOR_CLASSES = (
    ChastityNextLesbianEventSensor,
    ChastityNextGayEventSensor,
    ChastityNextBisexualEventSensor,
    ChastityNextTransgenderEventSensor,
    ChastityNextQueerEventSensor,
    ChastityNextIntersexEventSensor,
    ChastityNextAsexualEventSensor,
    ChastityNextPansexualEventSensor,
    ChastityNextNonBinaryEventSensor,
    ChastityNextAromanticEventSensor,
    ChastityNextGenderfluidEventSensor,
    ChastityNextSapphicEventSensor,
)


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
            name="Community Events & Sauna Calendar",
            manufacturer="Community Events & Sauna Calendar",
            configuration_url="https://github.com/jonny5509/community-events-sauna-calendar",
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
        end = event.get("end")
        return {
            "event_date": start.date().isoformat() if hasattr(start, "date") else str(start)[:10],
            "end_date": end.date().isoformat() if hasattr(end, "date") else str(end)[:10] if end else "",
            "location": event.get("location", ""),
            "source_url": event.get("url", ""),
            "source": event.get("source", ""),
            "sources": event.get("sources", []),
            "categories": event.get("categories", []),
        }



class ChastityNextKinkEventSensor(ChastityCalendarSensorBase):
    """Show the next discovered kink or fetish event."""

    _attr_name = "Next Kink/Fetish Event"
    _attr_icon = "mdi:calendar-heart"

    def _event(self):
        today = dt_util.now().date()
        events = self._events("kink", today, date(today.year + 2, 1, 1))
        upcoming = [event for event in events if event.end_datetime_local.date() > today]
        return min(upcoming, key=lambda event: event.start_datetime_local) if upcoming else None

    @property
    def native_value(self) -> str:
        event = self._event()
        return _sensor_event_name(event.summary) if event else "No upcoming kink/fetish event"

    @property
    def extra_state_attributes(self) -> dict:
        return self._event_attributes(self._event())


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up focused monthly, LGBTQ+, and category-specific event sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    preferences = {**entry.data, **entry.options}
    # Retire category-only entities now represented by the consolidated
    # next_lgbtq_event.next_events_by_category attribute. Keep the dedicated
    # furry sensor as it is useful independently.
    registry = er.async_get(hass)
    for suffix in (
        "next_lesbian_event", "next_gay_event", "next_bisexual_event",
        "next_transgender_event", "next_queer_event", "next_intersex_event",
        "next_asexual_event", "next_pansexual_event", "next_non-binary_event",
        "next_aromantic_event", "next_genderfluid_event", "next_sapphic_event",
    ):
        old_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{DOMAIN}_{entry.entry_id}_{suffix}"
        )
        if old_entity_id:
            registry.async_remove(old_entity_id)

    async_add_entities([
        ChastityOngoingMonthEventSensor(coordinator, entry.entry_id),
        ChastityNextMonthEventSensor(coordinator, entry.entry_id),
        ChastityPastLGBTQEventSensor(coordinator, entry.entry_id),
        ChastityNextLGBTQEventSensor(coordinator, entry.entry_id),
        ChastityNextFurryEventSensor(coordinator, entry.entry_id),
        ChastityNextKinkEventSensor(coordinator, entry.entry_id),
        ChastityNextSaunaEventSensor(coordinator, entry.entry_id),
        ChastityNearestSaunaSensor(hass, entry, preferences),
    ])
