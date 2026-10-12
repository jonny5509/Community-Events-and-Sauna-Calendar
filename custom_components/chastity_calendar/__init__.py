"""Community Events & Sauna Calendar integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PLATFORMS
from .discovery import async_discover_events

_LOGGER = logging.getLogger(__name__)
INITIAL_DISCOVERY_TIMEOUT = 60


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platforms immediately; discover remote events in the background."""
    preferences = {**entry.data, **entry.options}

    async def async_update_data():
        try:
            # Bound the complete discovery run so slow external services cannot
            # keep a refresh running indefinitely.
            async with asyncio.timeout(INITIAL_DISCOVERY_TIMEOUT):
                return await async_discover_events(
                    hass,
                    country=preferences.get("country", ""),
                    location=preferences.get("location", ""),
                    region=preferences.get("region", ""),
                    county=preferences.get("county", ""),
                    city=preferences.get("city", ""),
                    area=preferences.get("area", ""),
                    ticketmaster_api_key=preferences.get("ticketmaster_api_key", ""),
                )
        except TimeoutError:
            _LOGGER.warning(
                "Event discovery exceeded %s seconds; keeping the calendar available "
                "and trying again at the next refresh",
                INITIAL_DISCOVERY_TIMEOUT,
            )
            return []
        except Exception as err:
            raise UpdateFailed(f"Unable to search public event sources: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=f"{DOMAIN}_online_discovery",
        update_method=async_update_data,
        update_interval=None,
    )

    # Never await remote discovery during Home Assistant bootstrap. Initialize
    # entities with an empty result and search in a cancellable background task.
    coordinator.async_set_updated_data([])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.async_create_task(
        coordinator.async_request_refresh(),
        name=f"{DOMAIN} initial event discovery",
    )

    async def async_scheduled_refresh(_now):
        """Refresh at midnight and every six hours."""
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, async_scheduled_refresh, hour=[0, 6, 12, 18], minute=0, second=0)
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when preferences change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
