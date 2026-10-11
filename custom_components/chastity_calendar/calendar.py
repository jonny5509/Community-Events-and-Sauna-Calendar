"""Annual and discovered chastity-themed community calendar."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const import DOMAIN

# These are informational calendar entries. Several names are niche,
# community-created themes rather than official or universally observed events.
# End dates are inclusive in this list; Home Assistant all-day events use an
# exclusive end date, so one day is added when constructing each event.
EVENTS = [
    {
        "summary": "International Male Chastity Day",
        "start": (1, 14),
        "end": (1, 14),
        "description": "Informal community observance; not an official public holiday.",
        "category": "informal",
    },
    {
        "summary": "Jailbird January",
        "start": (1, 1),
        "end": (1, 31),
        "description": "Niche community-created monthly theme. Meaning and participation vary.",
        "category": "community-created",
    },
    {
        "summary": "Feminized February",
        "start": (2, 1),
        "end": (2, 28),
        "description": "Niche community-created theme; not a widely established annual event.",
        "category": "community-created",
    },
    {
        "summary": "Maleless March",
        "start": (3, 1),
        "end": (3, 31),
        "description": "Niche community-created theme; not a widely established annual event.",
        "category": "community-created",
    },
    {
        "summary": "Abstinence April",
        "start": (4, 1),
        "end": (4, 30),
        "description": "Informal abstinence-themed challenge. Rules vary by community.",
        "category": "community-created",
    },
    {
        "summary": "You May Not Cum",
        "start": (5, 1),
        "end": (5, 31),
        "description": "Wordplay-based community challenge; not an official observance.",
        "category": "community-created",
    },
    {
        "summary": "Summer Chastity Challenge",
        "start": (6, 1),
        "end": (6, 30),
        "description": "Suggested personal challenge idea; no widely established named event identified.",
        "category": "suggested",
    },
    {
        "summary": "Midyear Chastity Challenge",
        "start": (7, 1),
        "end": (7, 31),
        "description": "Suggested personal challenge idea; no widely established named event identified.",
        "category": "suggested",
    },
    {
        "summary": "Anal Only August",
        "start": (8, 1),
        "end": (8, 31),
        "description": "Niche sexual-themed internet challenge; not a recognised chastity observance.",
        "category": "community-created",
    },
    {
        "summary": "Sissy September",
        "start": (9, 1),
        "end": (9, 30),
        "description": "Niche online kink theme; not universally observed.",
        "category": "community-created",
    },
    {
        "summary": "Locktober",
        "start": (10, 1),
        "end": (10, 31),
        "description": "Widely discussed online chastity challenge. Participants may choose a consensual lockup or abstinence goal. Community challenge, not an official observance.",
        "category": "community challenge",
    },
    {
        "summary": "No Nut November",
        "start": (11, 1),
        "end": (11, 30),
        "description": "Widely known online abstinence challenge; chastity-device use is optional.",
        "category": "community challenge",
    },
    {
        "summary": "Denied December",
        "start": (12, 1),
        "end": (12, 31),
        "description": "Community-created theme; not an official observance.",
        "category": "community-created",
    },
    {
        "summary": "Chastity Advent Calendar",
        "start": (12, 1),
        "end": (12, 24),
        "description": "Suggested personal or couples idea: a daily consensual prompt or activity through 24 December.",
        "category": "suggested",
    },
]


def _event_for_year(item: dict, year: int) -> CalendarEvent:
    """Build an all-day event for a given year."""
    start_month, start_day = item["start"]
    end_month, end_day = item["end"]
    start = datetime(year, start_month, start_day)
    end = datetime(year, end_month, end_day) + timedelta(days=1)
    return CalendarEvent(
        summary=item["summary"],
        start=start,
        end=end,
        description=f'{item["description"]}\nCategory: {item["category"]}.',
    )


class ChastityChallengeCalendar(CalendarEntity):
    """Expose recurring annual challenge events."""

    _attr_has_entity_name = True
    _attr_name = "Challenges"
    _attr_icon = "mdi:calendar-heart"

    def __init__(self, coordinator) -> None:
        """Initialize the calendar."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_challenges"

    async_added_to_hass(self):
        """Refresh the calendar entity when online discoveries update."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_get_events(self, hass, start_date, end_date):
        """Return events overlapping the requested date range."""
        start_date = dt_util.as_local(start_date).replace(tzinfo=None)
        end_date = dt_util.as_local(end_date).replace(tzinfo=None)
        events = []
        for year in range(start_date.year, end_date.year + 1):
            for item in EVENTS:
                # Skip 29 February is not needed for the listed event dates.
                event = _event_for_year(item, year)
                if event.end > start_date and event.start < end_date:
                    events.append(event)
        for item in (self.coordinator.data or []):
            if item["end"] > start_date and item["start"] < end_date:
                events.append(CalendarEvent(
                    summary=item["summary"],
                    start=item["start"],
                    end=item["end"],
                    description=item["description"],
                ))
        return sorted(events, key=lambda event: event.start)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the calendar entity."""
    async_add_entities([ChastityChallengeCalendar(hass.data[DOMAIN][entry.entry_id])])
