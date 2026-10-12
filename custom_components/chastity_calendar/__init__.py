"""Community Events & Sauna Calendar integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS
from .discovery import async_discover_events

_LOGGER = logging.getLogger(__name__)
INITIAL_DISCOVERY_TIMEOUT = 60


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platforms immediately; discover remote events in the background."""
    preferences = {**entry.data, **entry.options}

    async def async_update_data():
        coordinator.last_discovery_attempt = dt_util.utcnow().isoformat()
        try:
            # Several public RSS endpoints may be slow or unavailable. Put a
            # hard limit on the whole discovery run, not just each HTTP call,
            # so a stalled source cannot hold setup or a refresh indefinitely.
            async with asyncio.timeout(INITIAL_DISCOVERY_TIMEOUT):
                events = await async_discover_events(
                    hass,
                    country=preferences.get("country", ""),
                    location=preferences.get("location", ""),
                    region=preferences.get("region", ""),
                    county=preferences.get("county", ""),
                    city=preferences.get("city", ""),
                    area=preferences.get("area", ""),
                    ticketmaster_api_key=preferences.get("ticketmaster_api_key", ""),
                )
            coordinator.last_successful_update = dt_util.utcnow().isoformat()
            coordinator.last_discovery_status = "success"
            coordinator.last_discovery_error = None
            return events
        except TimeoutError:
            coordinator.last_discovery_status = "timeout"
            coordinator.last_discovery_error = (
                f"Discovery exceeded {INITIAL_DISCOVERY_TIMEOUT} seconds; previous results retained."
            )
            _LOGGER.warning(
                "Event discovery exceeded %s seconds; keeping the calendar available "
                "with the events already loaded and trying again at the next refresh",
                INITIAL_DISCOVERY_TIMEOUT,
            )
            return coordinator.data or []
        except Exception as err:
            coordinator.last_discovery_status = "failed"
            coordinator.last_discovery_error = f"{type(err).__name__}: {err}"
            raise UpdateFailed(f"Unable to search public event sources: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=f"{DOMAIN}_online_discovery",
        update_method=async_update_data,
        update_interval=None,
    )

    # Do not await remote discovery during Home Assistant bootstrap. Set up
    # entities with an empty initial result, then perform the first search as
    # a cancellable background task. This avoids HA reporting that this
    # integration is still setting up while external search services hang.
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
