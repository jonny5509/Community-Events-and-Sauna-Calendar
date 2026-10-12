"""Community Events & Sauna Calendar integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS
from .discovery import async_discover_events

_LOGGER = logging.getLogger(__name__)
INITIAL_DISCOVERY_TIMEOUT = 180
DISCOVERY_RETRY_DELAY = 120


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platforms immediately; discover remote events in the background."""
    preferences = {**entry.data, **entry.options}

    async def async_update_data():
        coordinator.last_discovery_attempt = dt_util.utcnow().isoformat()
        try:
            # Discovery fans out across many public RSS searches. Give the
            # bounded batch enough time to complete, without blocking setup.
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
            _LOGGER.info("Event discovery completed successfully: %s events", len(events))
            return events
        except TimeoutError:
            coordinator.last_discovery_status = "timeout"
            coordinator.last_discovery_error = (
                f"Discovery exceeded {INITIAL_DISCOVERY_TIMEOUT} seconds; "
                f"retry scheduled in {DISCOVERY_RETRY_DELAY} seconds."
            )
            _LOGGER.warning(
                "Event discovery exceeded %s seconds; retaining %s existing events "
                "and scheduling a retry in %s seconds",
                INITIAL_DISCOVERY_TIMEOUT,
                len(coordinator.data or []),
                DISCOVERY_RETRY_DELAY,
            )

            # Previously an initial timeout left the coordinator empty until
            # the next six-hour refresh. Retry shortly so a slow first search
            # does not make the LGBTQ+ calendar appear permanently blank.
            def request_retry(_now):
                hass.async_create_task(
                    coordinator.async_request_refresh(),
                    name=f"{DOMAIN} discovery retry",
                )

            cancel_retry = async_call_later(hass, DISCOVERY_RETRY_DELAY, request_retry)
            entry.async_on_unload(cancel_retry)
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

    # Set up entities immediately; remote discovery runs in the background.
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
