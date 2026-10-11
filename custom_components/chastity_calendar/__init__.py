"""Chastity Challenge Calendar integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, PLATFORMS
from .discovery import async_discover_events
_LOGGER=logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up multi-source discovery and refresh every six hours."""
    preferences={**entry.data,**entry.options}
    async def async_update_data():
        try:
            return await async_discover_events(
                hass,
                country=preferences.get("country",""),
                location=preferences.get("location",""),
                ticketmaster_api_key=preferences.get("ticketmaster_api_key",""),
            )
        except Exception as err:
            raise UpdateFailed(f"Unable to search public event sources: {err}") from err
    coordinator=DataUpdateCoordinator(hass,logger=_LOGGER,name=f"{DOMAIN}_online_discovery",update_method=async_update_data,update_interval=None)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN,{})[entry.entry_id]=coordinator
    async def async_scheduled_refresh(_now):
        """Refresh at midnight and every six hours."""
        await coordinator.async_request_refresh()
    entry.async_on_unload(async_track_time_change(hass,async_scheduled_refresh,hour=[0,6,12,18],minute=0,second=0))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS)
    return True

async def async_reload_entry(hass: HomeAssistant,entry: ConfigEntry) -> None:
    """Reload when preferences change."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant,entry: ConfigEntry) -> bool:
    """Unload integration platforms."""
    unload_ok=await hass.config_entries.async_unload_platforms(entry,PLATFORMS)
    if unload_ok: hass.data.get(DOMAIN,{}).pop(entry.entry_id,None)
    return unload_ok
