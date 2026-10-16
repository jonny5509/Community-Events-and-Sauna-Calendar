"""Event Hub controls for the next discovered event."""
from __future__ import annotations

from datetime import date, datetime
from urllib.parse import quote_plus

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN


def _event_date(value) -> date | None:
    """Convert a discovered start value into a local calendar date."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = dt_util.as_local(value)
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


class EventHubButton(ButtonEntity):
    """Base class for event-specific notification controls."""

    _attr_has_entity_name = True
    event_kind = "event"
    action = "info"

    def __init__(self, hass, coordinator, entry) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{self.event_kind}_{self.action}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Chastity Events",
            manufacturer="Chastity Events",
            entry_type=None,
            configuration_url="https://github.com/jonny5509/Chastity-Events",
        )

    def _next_record(self) -> dict | None:
        """Find the next valid event record of this button's kind."""
        today = dt_util.now().date()
        matches = []
        for item in self.coordinator.data or []:
            if not isinstance(item, dict):
                continue
            start = _event_date(item.get("start"))
            if start is None or start < today:
                continue
            searchable = " ".join(str(item.get(key, "")) for key in (
                "summary", "description", "category", "location"
            )) + " " + " ".join(str(value) for value in item.get("categories", []))
            matches.append((start, item))
        return min(matches, key=lambda pair: pair[0])[1] if matches else None

    async def async_press(self) -> None:
        """Show a persistent notification with this event's real links."""
        item = self._next_record()
        if not item:
            await self._notify(
                "No upcoming event found",
                "No matching upcoming event is currently available. Try again after the next discovery refresh.",
            )
            return

        title = str(item.get("summary") or "Community event")
        start = _event_date(item.get("start"))
        location = str(item.get("location") or "").strip()
        url = str(item.get("url") or "").strip()
        if not url:
            links = item.get("source_links") or []
            if isinstance(links, str):
                url = links.strip()
            elif isinstance(links, (list, tuple)) and links:
                url = str(links[0]).strip()
        description = str(item.get("description") or "").strip()
        parts = [f"**{title}**"]
        if start:
            parts.append(f"**Date:** {start.isoformat()}")
        if location:
            parts.append(f"**Location:** {location}")
        if description and self.action == "info":
            parts.append(description)
        if self.action == "directions":
            if location:
                map_url = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(location)
                parts.append(f"[Get directions]({map_url})")
            else:
                parts.append("This event does not currently include a venue or address, so directions are unavailable.")
        elif url:
            parts.append(f"[Event information / organiser website]({url})")
        else:
            parts.append("No event webpage was provided by the source.")
        source = str(item.get("source") or "").strip()
        if source:
            parts.append(f"Source: {source}")
        await self._notify(title, "\n\n".join(parts))

    async def _notify(self, title: str, message: str) -> None:
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {"title": title, "message": message, "notification_id": self._attr_unique_id},
        )


class NextEventInformationButton(EventHubButton):
    """Show details and the source URL for the next discovered event."""

    _attr_name = "Next Event Information"
    _attr_icon = "mdi:information-outline"
    event_kind = "event"
    action = "info"


class NextEventDirectionsButton(EventHubButton):
    """Show a map link for the next discovered event when a location exists."""

    _attr_name = "Next Event Directions"
    _attr_icon = "mdi:map-marker-directions"
    event_kind = "event"
    action = "directions"


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Register Event Hub controls as device-associated button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        NextEventInformationButton(hass, coordinator, entry),
        NextEventDirectionsButton(hass, coordinator, entry),
    ])
