"""Community Events & Sauna Calendar integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS
from .attendance import async_setup_attendance, async_unload_attendance
from .discovery import async_discover_events
from .participation import (
    async_has_verified_active_session,
    async_load_crown_days,
    async_save_crown_days,
)

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
            # the next scheduled refresh. Retry shortly so a slow first search
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

    # Crown history is persisted separately from remote event discovery.
    coordinator.crown_days = await async_load_crown_days(hass, entry.entry_id)

    async def async_check_crowns(_now=None):
        """Record at most one crown per local day after a verified active session."""
        try:
            if not await async_has_verified_active_session(hass, preferences):
                return
            today = dt_util.now().date().isoformat()
            if today in coordinator.crown_days:
                return
            updated_days = set(coordinator.crown_days)
            updated_days.add(today)
            await async_save_crown_days(hass, entry.entry_id, updated_days)
            coordinator.crown_days = updated_days
            # Notify calendar entities so the new all-day crown appears immediately.
            coordinator.async_set_updated_data(coordinator.data or [])
            _LOGGER.info("Recorded a verified participation crown for %s", today)
        except Exception:
            # A provider/storage failure must never create a crown.
            _LOGGER.warning("Unable to verify or record today's participation crown")

    # Restore attendance choices and schedule any outstanding 24-hour reminders.
    await async_setup_attendance(hass, entry, coordinator)

    # Set up entities immediately; remote discovery runs in the background.
    coordinator.async_set_updated_data([])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.async_create_task(
        coordinator.async_request_refresh(),
        name=f"{DOMAIN} initial event discovery",
    )

    async def async_scheduled_refresh(_now):
        """Refresh every three hours, starting at midnight."""
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, async_scheduled_refresh, hour=[0, 3, 6, 9, 12, 15, 18, 21], minute=0, second=0)
    )
    # Check periodically so a session that starts during the day can be recorded.
    entry.async_on_unload(
        async_track_time_change(hass, async_check_crowns, minute=[0, 30], second=0)
    )
    hass.async_create_task(
        async_check_crowns(), name=f"{DOMAIN} active-session crown check"
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
        await async_unload_attendance(hass, entry)
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
