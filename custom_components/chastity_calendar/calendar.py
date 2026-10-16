"""Annual and discovered chastity-themed community calendar."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.device_registry import DeviceInfo
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
    {
        "summary": "International Fetish Day",
        "start": (1, 1),
        "end": (1, 1),
        "recurrence": "third_friday_january",
        "description": "Community observance for fetish diversity and education. Observed on the third Friday in January; community observance, not an official holiday.",
        "category": "kink observance",
    },
    {
        "summary": "World BDSM Day",
        "start": (7, 24),
        "end": (7, 24),
        "description": "Community-referenced BDSM awareness date. Observance and recognition vary; use as an informational calendar entry.",
        "category": "kink observance",
    },
    {
        "summary": "Kink Consent & Safety Check-in",
        "start": (4, 1),
        "end": (4, 1),
        "description": "Suggested annual reminder to review consent, boundaries, safewords, aftercare, and risk-aware practices with partners.",
        "category": "suggested",
    },
    {
        "summary": "Leather & Gear Appreciation Day",
        "start": (5, 1),
        "end": (5, 1),
        "description": "Suggested community theme day for leather, boots, uniforms, and fetish fashion; not an official observance.",
        "category": "suggested",
    },
    {
        "summary": "Rope & Shibari Education Day",
        "start": (3, 1),
        "end": (3, 1),
        "description": "Suggested reminder to explore consent-led rope education, communication, and safety; not an official observance.",
        "category": "suggested",
    },
    {
        "summary": "Rubber & Latex Appreciation Day",
        "start": (8, 1),
        "end": (8, 1),
        "description": "Suggested theme day for rubber, latex, PVC, and fetish fashion; not an official observance.",
        "category": "suggested",
    },
    {
        "summary": "Power Exchange Reflection Day",
        "start": (9, 1),
        "end": (9, 1),
        "description": "Suggested reminder for consenting adults to review roles, boundaries, communication, and relationship agreements.",
        "category": "suggested",
    },
    {
        "summary": "Fetish Community & Gear Social Reminder",
        "start": (2, 1),
        "end": (2, 1),
        "description": "Suggested prompt to look for local leather, rubber, pup-play, rope, and other adult kink community socials.",
        "category": "suggested",
    }
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


def _as_aware_local(value: datetime) -> datetime:
    """Return a datetime with Home Assistant's local timezone attached.

    Naive source datetimes are treated as local wall time. Attaching the
    configured timezone before conversion avoids silently interpreting an
    event's displayed local time as UTC.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(value)


def _is_lgbtq_event(item: dict) -> bool:
    """Return whether discovered metadata or the listing itself identifies an LGBTQ+ event."""
    lgbtq_categories = {
        "pride", "lgbtq", "lgbtq+", "lgbtqia", "gay", "lesbian", "bisexual",
        "transgender", "queer", "pansexual", "non-binary", "nonbinary",
        "intersex", "asexual", "aromantic", "genderfluid", "agender", "sapphic",
    }
    categories = {str(value).casefold() for value in item.get("categories", [])}
    category = str(item.get("category", "")).casefold()
    if category in lgbtq_categories or categories.intersection(lgbtq_categories):
        return True

    text = " ".join(str(item.get(key, "")) for key in (
        "summary", "title", "description", "location", "url"
    )).casefold()
    # Use specific phrases/words so short abbreviations like "bi" do not
    # accidentally classify unrelated events.
    terms = (
        "lgbtq", "lgbtqia", "lgbt+", "queer", "pride", "gay", "lesbian",
        "bisexual", "bi visibility", "pansexual", "omnisexual", "transgender",
        "transmasc", "transfem", "trans pride", "non-binary", "nonbinary",
        "genderqueer", "genderfluid", "agender", "intersex", "asexual",
        "aromantic", "demisexual", "demiromantic", "graysexual", "greysexual",
        "two-spirit", "two spirit", "sapphic", "wlw", "mlm", "drag show",
        "drag night", "voguing", "queer film", "queer art", "gender affirming",
        "hiv awareness", "hiv support",
    )
    return any(term in text for term in terms)


def _is_kink_event(item: dict) -> bool:
    """Return whether a discovered event is specifically kink/fetish related."""
    keywords = (
        "kink", "fetish", "bdsm", "leather", "latex", "rubber", "shibari",
        "rope play", "pup play", "puppy play", "dominatrix", "dominant",
        "submission", "submissive", "power exchange", "locktober", "chastity",
        "adult play party", "fetish market", "fetish social", "dungeon",
        "furry", "furmeet", "fursuit",
    )
    categories = {str(value).casefold() for value in item.get("categories", [])}
    category = str(item.get("category", "")).casefold()
    text = " ".join(str(item.get(key, "")) for key in ("summary", "title", "description")).casefold()
    return (
        category in {"kink", "fetish", "bdsm", "chastity"}
        or bool(categories.intersection({"kink", "fetish", "bdsm", "chastity"}))
        or any(keyword in text for keyword in keywords)
    )


def _event_for_year(item: dict, year: int) -> CalendarEvent:
    """Build an all-day event using dates and an exclusive end date."""
    start_month, start_day = item["start"]
    end_month, end_day = item["end"]
    if item.get("recurrence") == "third_friday_january":
        # January 1 weekday offset to Friday, then two further weeks.
        start = date(year, 1, 1) + timedelta(days=(4 - date(year, 1, 1).weekday()) % 7 + 14)
        end = start
    else:
        start = date(year, start_month, start_day)
        end = date(year, end_month, end_day)
    end += timedelta(days=1)
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

    def __init__(self, coordinator, calendar_type: str, entry_id: str) -> None:
        """Initialize one of the integration's separate calendars."""
        self.coordinator = coordinator
        self.calendar_type = calendar_type
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Community Events Calendar",
            manufacturer="Community Events Calendar",
            configuration_url="https://github.com/jonny5509/community-events-sauna-calendar",
        )
        if calendar_type == "pride":
            self._attr_name = "LGBTQ+ Events"
            self._attr_icon = "mdi:flag"
        elif calendar_type == "kink":
            self._attr_name = "Kink & Fetish Events"
            self._attr_icon = "mdi:calendar-heart"
        else:
            self._attr_name = "Monthly Events"
        self._attr_unique_id = f"{DOMAIN}_{calendar_type}"

    @property
    def extra_state_attributes(self) -> dict:
        """Expose saved attendance choices for dashboard cards."""
        records = getattr(self.coordinator, "attendance", {})
        return {
            "attendance": [
                {
                    "summary": record.get("summary", ""),
                    "start": record.get("start", ""),
                    "status": record.get("status", ""),
                    "url": record.get("url", ""),
                }
                for record in records.values()
                if isinstance(record, dict)
            ],
        }

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
            is_lgbtq = _is_lgbtq_event(item)
            is_kink = _is_kink_event(item)
            if self.calendar_type == "monthly" and (is_lgbtq or is_kink):
                continue
            if self.calendar_type == "kink":
                if not is_kink:
                    continue
            elif self.calendar_type == "pride":
                if not is_lgbtq or is_kink:
                    continue
            raw_start = item["start"]
            raw_end = item["end"]
            # Date-only source results are stored internally as midnight
            # datetimes for compatibility with discovery/deduplication, but must
            # be emitted as date values so Home Assistant renders them all-day.
            if item.get("all_day"):
                event_start = raw_start.date() if isinstance(raw_start, datetime) else raw_start
                event_end = raw_end.date() if isinstance(raw_end, datetime) else raw_end
                overlaps = event_end > start_day and event_start < end_day
            elif isinstance(raw_start, datetime) or isinstance(raw_end, datetime):
                # Home Assistant requires timezone-aware datetimes for timed
                # CalendarEvents. Interpret naive source times in HA's local zone.
                event_start = _as_aware_local(
                    raw_start if isinstance(raw_start, datetime)
                    else datetime.combine(raw_start, datetime.min.time())
                )
                event_end = _as_aware_local(
                    raw_end if isinstance(raw_end, datetime)
                    else datetime.combine(raw_end, datetime.min.time())
                )
                range_start = _as_aware_local(datetime.combine(start_day, datetime.min.time()))
                range_end = _as_aware_local(datetime.combine(end_day, datetime.min.time()))
                overlaps = event_end > range_start and event_start < range_end
            else:
                event_start = raw_start
                event_end = raw_end
                overlaps = event_end > start_day and event_start < end_day
            if overlaps:
                # Preserve the original event span. Single-day events remain
                # single-day entries; multi-day events span their full dates so
                # Home Assistant can render them as bars in month views.
                events.append(CalendarEvent(
                    summary=item["summary"],
                    start=event_start,
                    end=event_end,
                    description=(
                        f'{item["description"]}\n\nWebsite: {item.get("url") or item.get("source_url")}'
                        if item.get("url") or item.get("source_url")
                        else item["description"]
                    ),
                    location=item.get("location") or "",
                ))
        # Daily crowns appear only on the monthly challenge calendar. A crown
        # means an active session was verified at least once on that local date;
        # it does not claim uninterrupted activity for the entire day.
        if self.calendar_type == "monthly":
            for value in getattr(self.coordinator, "crown_days", set()):
                try:
                    crown_day = date.fromisoformat(value)
                except (TypeError, ValueError):
                    continue
                if start_day <= crown_day < end_day:
                    month_event = next(
                        (item for item in EVENTS if item["start"][0] == crown_day.month),
                        None,
                    )
                    month_name = month_event["summary"] if month_event else "Monthly challenge"
                    events.append(CalendarEvent(
                        summary=f"👑 {month_name} participation crown",
                        start=crown_day,
                        end=crown_day + timedelta(days=1),
                        description=(
                            "An active lock session was verified through a configured "
                            "service at least once during this local calendar day."
                        ),
                        location="",
                    ))
        return sorted(events, key=lambda event: event.start_datetime_local)

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
    """Set up separate monthly, LGBTQ+, and kink/fetish calendars."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ChastityChallengeCalendar(coordinator, "monthly", entry.entry_id),
        ChastityChallengeCalendar(coordinator, "pride", entry.entry_id),
        ChastityChallengeCalendar(coordinator, "kink", entry.entry_id),
    ])
