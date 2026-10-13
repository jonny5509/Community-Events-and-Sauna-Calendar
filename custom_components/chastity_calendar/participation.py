"""Read-only checks for verified active lock sessions and daily crown history."""
from __future__ import annotations

import logging
from datetime import date

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


def emlalock_session_active(payload: object) -> bool:
    """Return true only when EmlaLock reports an open session object."""
    if not isinstance(payload, dict):
        return False
    session = payload.get("chastitysession")
    if not isinstance(session, dict):
        return False
    # EmlaLock's /info response includes chastitysession when in a session.
    # closedate=0 is the documented response shape for an unclosed session.
    startdate = session.get("startdate")
    return (
        session.get("closedate") == 0
        and isinstance(startdate, (int, float))
        and startdate > 0
    )


def chastify_session_active(payload: object) -> bool:
    """Return true when Chastify's current-session endpoint confirms a lock."""
    if not isinstance(payload, dict):
        return False
    # /api/apps/v1/session is specifically the current active lock context.
    # Require the documented lock and lockData objects, not a generic 200.
    return isinstance(payload.get("lock"), dict) and isinstance(
        payload.get("lockData"), dict
    )


def chaster_has_active_lock(payload: object) -> bool:
    """Return true only for a Chaster lock with the explicit 'locked' status."""
    if not isinstance(payload, list):
        return False
    return any(
        isinstance(lock, dict) and lock.get("status") == "locked"
        for lock in payload
    )


async def async_has_verified_active_session(hass, preferences: dict) -> bool:
    """Check configured services. API failures never count as participation."""
    session = async_get_clientsession(hass)
    selected = preferences.get("participation_providers", [])
    if not isinstance(selected, (list, tuple, set)):
        selected = []

    emla_user = str(preferences.get("emlalock_userid", "")).strip()
    emla_key = str(preferences.get("emlalock_api_key", "")).strip()
    if "emlalock" in selected and emla_user and emla_key:
        try:
            async with session.get(
                "https://api.emlalock.com/info",
                params={"userid": emla_user, "apikey": emla_key},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                payload = await response.json()
            if emlalock_session_active(payload):
                return True
        except (aiohttp.ClientError, TimeoutError, ValueError):
            # Do not log the URL: EmlaLock requires its API key in query params.
            _LOGGER.warning("Unable to verify an EmlaLock session; no crown awarded")

    chastify_token = str(preferences.get("chastify_dev_token", "")).strip()
    if "chastify" in selected and chastify_token:
        headers = {"Authorization": f"Bearer {chastify_token}"}
        lock_id = str(preferences.get("chastify_lock_id", "")).strip()
        if lock_id:
            headers["x-chastify-lock-id"] = lock_id
        try:
            async with session.get(
                "https://chastify.net/api/apps/v1/session",
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                payload = await response.json()
            if chastify_session_active(payload):
                return True
        except (aiohttp.ClientError, TimeoutError, ValueError):
            _LOGGER.warning("Unable to verify a Chastify session; no crown awarded")

    chaster_token = str(preferences.get("chaster_access_token", "")).strip()
    if "chaster" in selected and chaster_token:
        try:
            async with session.get(
                "https://api.chaster.app/locks",
                params={"status": "active"},
                headers={"Authorization": f"Bearer {chaster_token}"},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                payload = await response.json()
            if chaster_has_active_lock(payload):
                return True
        except (aiohttp.ClientError, TimeoutError, ValueError):
            _LOGGER.warning("Unable to verify a Chaster session; no crown awarded")

    return False


async def async_load_crown_days(hass, entry_id: str) -> set[str]:
    """Load the persistent ISO date list of days with verified participation."""
    store = Store(hass, 1, f"{DOMAIN}_{entry_id}_crown_days")
    data = await store.async_load()
    days = data.get("days", []) if isinstance(data, dict) else []
    return {value for value in days if isinstance(value, str) and _valid_iso_date(value)}


def _valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


async def async_save_crown_days(hass, entry_id: str, days: set[str]) -> None:
    """Persist crown dates without storing API credentials or session details."""
    store = Store(hass, 1, f"{DOMAIN}_{entry_id}_crown_days")
    await store.async_save({"days": sorted(days)})
