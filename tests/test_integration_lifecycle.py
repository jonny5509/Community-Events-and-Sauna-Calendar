"""End-to-end Home Assistant setup and unload smoke tests."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chastity_calendar.const import DOMAIN


@pytest.mark.asyncio
async def test_config_entry_setup_creates_entities_and_unloads_cleanly(
    hass, enable_custom_integrations
):
    """Exercise the real HA config-entry and platform lifecycle without network calls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Community Events Calendar",
        data={
            "country": "United Kingdom",
            "location": "",
            "region": "",
            "county": "",
            "city": "",
            "area": "",
            "ticketmaster_api_key": "",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.chastity_calendar.async_discover_events",
        new=AsyncMock(return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.entry_id in hass.data[DOMAIN]
        assert len(hass.states.async_entity_ids("calendar")) >= 3
        assert any(
            "ongoing_month_event" in entity_id
            for entity_id in hass.states.async_entity_ids("sensor")
        )

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
