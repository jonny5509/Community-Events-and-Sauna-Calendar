"""Persistent event attendance choices and 24-hour reminders."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SERVICE_SET_ATTENDANCE = "set_event_attendance"
VALID_STATUSES = {"interested", "going", "not_going"}
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("summary"): vol.All(str, vol.Length(min=1, max=500)),
        vol.Required("start"): str,
        vol.Required("status"): vol.In(VALID_STATUSES),
        vol.Optional("url", default=""): str,
    }
)


def _event_id(summary: str, start: datetime, url: str = "") -> str:
    """Build a stable identifier for one event occurrence."""
    identity = f"{summary.strip().casefold()}|{start.isoformat()}|{url.strip().casefold()}"
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


def _parse_start(value: str) -> datetime:
    """Parse a timestamp and interpret naive values in Home Assistant local time."""
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        raise vol.Invalid("start must be an ISO date or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(parsed)


async def async_setup_attendance(hass: HomeAssistant, entry, coordinator) -> None:
    """Restore event attendance and register its service."""
    store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_attendance")
    saved = await store.async_load()
    records: dict[str, dict[str, Any]] = saved if isinstance(saved, dict) else {}
    coordinator.attendance = records
    coordinator.attendance_store = store
    coordinator.attendance_cancel_callbacks = {}
    coordinator.attendance_entry_id = entry.entry_id

    async def async_persist() -> None:
        await store.async_save(records)

    async def async_notify(record: dict[str, Any]) -> None:
        title = f"Event tomorrow: {record['summary']}"
        start = _parse_start(record["start"])
        local_start = dt_util.as_local(start).strftime("%A %d %B at %H:%M")
        message = (
            f"You're marked as going to **{record['summary']}**.\n\n"
            f"**Starts:** {local_start}"
        )
        if record.get("url"):
            message += f"\n\n[Event information]({record['url']})"

        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": f"{DOMAIN}_attendance_{record['id']}",
            },
        )

        notify_services = hass.services.async_services().get("notify", {})
        mobile_services = [
            name for name in notify_services if name.startswith("mobile_app_")
        ]
        payload = {
            "title": title,
            "message": message.replace("**", "").replace("\n\n", " "),
            "data": {"tag": f"{DOMAIN}_attendance_{record['id']}"},
        }
        for service in mobile_services:
            try:
                await hass.services.async_call("notify", service, payload)
            except Exception:
                _LOGGER.warning("Unable to send event reminder through %s", service)

        if not mobile_services:
            _LOGGER.warning(
                "No Home Assistant mobile app notify service is configured; "
                "the dashboard reminder was created, but no phone notification was sent."
            )

    def schedule(record: dict[str, Any]) -> None:
        """Schedule one reminder if the event is still more than 24 hours away."""
        if record.get("status") != "going" or record.get("reminder_sent"):
            return
        try:
            event_start = _parse_start(record["start"])
        except (TypeError, ValueError, vol.Invalid):
            _LOGGER.warning("Skipping reminder with invalid start for %s", record.get("summary"))
            return
        reminder_at = event_start - timedelta(hours=24)
        if reminder_at <= dt_util.now():
            # The exact 24-hour point has already passed; do not send a late reminder.
            return

        def fire(_now) -> None:
            async def async_fire() -> None:
                current = records.get(record["id"])
                if not current or current.get("status") != "going" or current.get("reminder_sent"):
                    return
                current["reminder_sent"] = True
                await async_persist()
                await async_notify(current)

            hass.async_create_task(async_fire(), name=f"{DOMAIN} event reminder")

        coordinator.attendance_cancel_callbacks[record["id"]] = async_track_point_in_utc_time(
            hass, fire, dt_util.as_utc(reminder_at)
        )

    for record in records.values():
        if isinstance(record, dict):
            schedule(record)

    async def async_set_attendance(call: ServiceCall) -> None:
        """Persist attendance status and schedule/cancel reminders."""
        data = SERVICE_SCHEMA(call.data)
        start = _parse_start(data["start"])
        summary = data["summary"].strip()
        url = data["url"].strip()
        identifier = _event_id(summary, start, url)
        previous = coordinator.attendance_cancel_callbacks.pop(identifier, None)
        if previous:
            previous()

        records[identifier] = {
            "id": identifier,
            "summary": summary,
            "start": start.isoformat(),
            "url": url,
            "status": data["status"],
            "reminder_sent": False,
        }
        if data["status"] == "going":
            schedule(records[identifier])
        await async_persist()
        coordinator.async_set_updated_data(coordinator.data or [])

    if not hass.services.has_service(DOMAIN, SERVICE_SET_ATTENDANCE):
        hass.services.async_register(
            DOMAIN, SERVICE_SET_ATTENDANCE, async_set_attendance, schema=SERVICE_SCHEMA
        )


async def async_unload_attendance(hass: HomeAssistant, entry) -> None:
    """Cancel in-memory timers when the integration is unloaded."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator:
        for cancel in coordinator.attendance_cancel_callbacks.values():
            cancel()
        coordinator.attendance_cancel_callbacks.clear()
    # The integration currently permits one config entry, so its service is
    # removed on unload to avoid retaining a callback to a stale coordinator.
    if hass.services.has_service(DOMAIN, SERVICE_SET_ATTENDANCE):
        hass.services.async_remove(DOMAIN, SERVICE_SET_ATTENDANCE)
