"""Manual refresh button for online event and sauna discovery."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN


class FetchSaunaEventsButton(ButtonEntity):
    """Request a fresh lookup of online events, including sauna listings."""

    _attr_has_entity_name = True
    _attr_name = "Fetch Sauna Events"
    _attr_icon = "mdi:calendar-refresh"

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_fetch_sauna_events"

    async def async_press(self) -> None:
        """Refresh the shared event discovery coordinator immediately."""
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the manual event refresh button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FetchSaunaEventsButton(coordinator)])
