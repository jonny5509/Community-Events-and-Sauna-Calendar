"""Diagnostics support for Community Events & Sauna Calendar."""
from __future__ import annotations

from collections import Counter

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return useful troubleshooting data without exposing credentials."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    events = (coordinator.data or []) if coordinator else []

    source_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    for event in events:
        sources = event.get("sources") or [event.get("source", "unknown")]
        for source in sources:
            if source:
                source_counts[str(source)] += 1
        categories = event.get("categories") or [event.get("category", "uncategorized")]
        for category in categories:
            if category:
                category_counts[str(category)] += 1

    # Never include the Ticketmaster API key or raw config-entry options.
    config = {
        key: value
        for key, value in {**entry.data, **entry.options}.items()
        if "key" not in key.casefold() and "token" not in key.casefold()
        and "secret" not in key.casefold() and "password" not in key.casefold()
    }

    return {
        "config": config,
        "discovery": {
            "status": getattr(coordinator, "last_discovery_status", "not_started"),
            "last_attempt": getattr(coordinator, "last_discovery_attempt", None),
            "last_successful_update": getattr(coordinator, "last_successful_update", None),
            "last_error": getattr(coordinator, "last_discovery_error", None),
            "coordinator_last_update_success": (
                coordinator.last_update_success if coordinator else None
            ),
            "event_count": len(events),
            "events_by_source": dict(source_counts),
            "events_by_category": dict(category_counts),
        },
    }
