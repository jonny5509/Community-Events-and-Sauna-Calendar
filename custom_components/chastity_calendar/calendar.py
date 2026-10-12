"""Annual and discovered chastity-themed community calendar."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.event import async_track_time_change
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

# Reliable annual observances ensure this calendar has upcoming events even
# when public RSS search results contain no parseable dates.
PRIDE_EVENTS = [
    {
        "summary": "Transgender Day of Visibility",
        "start": (3, 31),
        "end": (3, 31),
        "description": "Annual day recognising transgender people and raising awareness of discrimination.",
        "category": "pride",
    },
    {
        "summary": "International Day Against Homophobia, Biphobia and Transphobia",
        "start": (5, 17),
        "end": (5, 17),
        "description": "Annual day promoting LGBTQ+ rights and opposing anti-LGBTQ+ discrimination.",
        "category": "pride",
    },
    {
        "summary": "Pride Month",
        "start": (6, 1),
        "end": (6, 30),
        "description": "Annual LGBTQ+ Pride observance. Local Pride events take place on different dates.",
        "category": "pride",
    },
    {
        "summary": "International Lesbian Day",
        "start": (10, 8),
        "end": (10, 8),
        "description": "Annual observance celebrating lesbian communities.",
        "category": "pride",
    },
    {
        "summary": "National Coming Out Day",
        "start": (10, 11),
        "end": (10, 11),
        "description": "Annual LGBTQ+ awareness day observed on 11 October.",
        "category": "pride",
    },
    {
        "summary": "Transgender Day of Remembrance",
        "start": (11, 20),
        "end": (11, 20),
        "description": "Annual day remembering transgender people lost to anti-transgender violence.",
        "category": "pride",
    },
    {
        "summary": "World AIDS Day",
        "start": (12, 1),
        "end": (12, 1),
        "description": "Annual day of awareness and remembrance related to HIV and AIDS.",
        "category": "pride",
    },
    {
        "summary": "Bisexual Visibility Day",
        "start": (9, 23),
        "end": (9, 23),
        "description": "Annual observance celebrating bisexual visibility and community.",
        "category": "pride",
    },
]


def _event_for_year(item: dict, year: int) -> CalendarEvent:
    """Build an all-day event using dates and an exclusive end date."""
    start_month, start_day = item["start"]
    end_month, end_day = item["end"]
    start = date(year, start_month, start_day)
    end = date(year, end_month, end_day) + timedelta(days=1)
    return CalendarEvent(
        summary=item["summary"],
        start=start,
        end=end,
        description=f'{item["description"]}\nCategory: {item["category"]}.',
    )


class ChastityChallengeCalendar(CalendarEntity):
    """Expose recurring annual challenge events."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-heart"

    def __init__(self, coordinator, calendar_type: str) -> None:
        """Initialize one of the integration's separate calendars."""
        self.coordinator = coordinator
        self.calendar_type = calendar_type
        if calendar_type == "pride":
            self._attr_name = "Pride EC Events"
            self._attr_icon = "mdi:flag"
        elif calendar_type == "sauna":
            self._attr_name = "Sauna Events"
            self._attr_icon = "mdi:hot-tub"
        else:
            self._attr_name = "Monthly Events"
        self._attr_unique_id = f"{DOMAIN}_{calendar_type}"

    def _events_between(self, start_day: date, end_day: date) -> list[CalendarEvent]:
        """Build events overlapping a date range (end is exclusive)."""
        events = []
        annual_events = (
            EVENTS if self.calendar_type == "monthly"
            else PRIDE_EVENTS if self.calendar_type == "pride"
            else []
        )
        for year in range(start_day.year, end_day.year + 1):
            for item in annual_events:
                event = _event_for_year(item, year)
                if event.end > start_day and event.start < end_day:
                    events.append(event)

        for item in (self.coordinator.data or []):
            # Keep sauna listings in their own calendar rather than mixing them
            # into Monthly Events. Pride remains a separate focused calendar.
            categories = set(item.get("categories", []))
            is_sauna = item.get("category") == "sauna" or "sauna" in categories
            if self.calendar_type == "monthly" and is_sauna:
                continue
            if self.calendar_type == "sauna" and not is_sauna:
                continue
            if self.calendar_type == "pride" and not (
                item.get("category") in {"pride", "gay", "lesbian", "bisexual", "transgender", "queer", "lgbtq"}
                or categories.intersection({"pride", "lgbtq", "gay", "lesbian", "bisexual", "transgender", "queer"})
            ):
                continue
            raw_start = item["start"]
            raw_end = item["end"]
            event_start = raw_start.date() if isinstance(raw_start, datetime) else raw_start
            event_end = raw_end.date() if isinstance(raw_end, datetime) else raw_end
            if event_end > start_day and event_start < end_day:
                events.append(CalendarEvent(
                    summary=item["summary"],
                    start=event_start,
                    end=event_end,
                    description=item["description"],
                    location=item.get("location") or "",
                ))
        return sorted(events, key=lambda event: event.start)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event for the entity state."""
        now = dt_util.now()
        today = now.date()
        # Include the next two calendar years so the next event is available
        # even near the end of December.
        candidates = self._events_between(date(today.year, 1, 1), date(today.year + 2, 1, 1))
        for event in candidates:
            if event.end_datetime_local > now:
                return event
        return None

    async def async_added_to_hass(self):
        """Refresh the calendar entity when online discoveries update."""
        await super().async_added_to_hass()
        # Recompute the current/next event when time crosses a date boundary,
        # as well as whenever the discovery coordinator publishes new data.
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._scheduled_state_refresh,
                hour=[0, 6, 12, 18], minute=0, second=0,
            )
        )

    def _handle_coordinator_update(self) -> None:
        """Refresh state when discovery data changes, including after re-enable."""
        self.async_write_ha_state()

    async def _scheduled_state_refresh(self, _now) -> None:
        """Refresh the entity state as upcoming events change over time."""
        self._handle_coordinator_update()

    async def async_get_events(self, hass, start_date, end_date):
        """Return all-day events overlapping the requested datetime range."""
        # CalendarEntity receives timezone-aware datetimes. Compare date-only
        # events against the full datetime bounds so the final day is not lost
        # when a caller's end time is before midnight.
        start_day = dt_util.as_local(start_date).date()
        end_day = dt_util.as_local(end_date).date()
        events = self._events_between(start_day, end_day + timedelta(days=1))
        return [
            event for event in events
            if event.end_datetime_local > start_date
            and event.start_datetime_local < end_date
        ]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up monthly, Pride, and sauna event calendars."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ChastityChallengeCalendar(coordinator, "monthly"),
        ChastityChallengeCalendar(coordinator, "pride"),
        ChastityChallengeCalendar(coordinator, "sauna"),
    ])
