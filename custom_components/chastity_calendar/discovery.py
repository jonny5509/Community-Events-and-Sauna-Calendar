"""Best-effort discovery of publicly indexed, dated community events."""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

# Google News exposes public RSS search results. This is a useful index, not
# exhaustive web coverage; results are included only when a future date can
# be extracted explicitly from the title or snippet.
SEARCHES = (
    '"chastity" event',
    '"Locktober" event',
    '"male chastity" event',
    '"chastity challenge" dates',
    '"No Nut November" event',
    '"kink event" chastity',
    '"chastity" convention OR meetup OR contest',
    '"Pride" festival parade 2027',
    '"LGBTQ" events festival 2027',
    '"LGBTQIA" Pride events dates',
    '"Trans Pride" events 2027',
    '"Bi Pride" OR "Lesbian Pride" events',
    '"Pride Month" events dates',
    '"LGBTQ History Month" events',
    '"Trans Day of Visibility" event',
    '"International Day Against Homophobia" event',
    '"Bi Visibility Day" event',
    '"Trans Day of Remembrance" event',
)
MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
DATE_PATTERNS = (
    re.compile(rf"\b({MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b", re.I),
    re.compile(rf"\b(\d{{1,2}})\s+({MONTHS})[,]?\s+(20\d{{2}})\b", re.I),
    re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),
)


def _find_future_date(text: str, today: datetime):
    """Return an explicit date in text if it is today or in the future."""
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                if pattern is DATE_PATTERNS[0]:
                    found = datetime.strptime(
                        f"{match.group(1)} {match.group(2)} {match.group(3)}",
                        "%B %d %Y",
                    )
                elif pattern is DATE_PATTERNS[1]:
                    found = datetime.strptime(
                        f"{match.group(2)} {match.group(1)} {match.group(3)}",
                        "%B %d %Y",
                    )
                else:
                    found = datetime.strptime(match.group(0), "%Y-%m-%d")
            except ValueError:
                continue
            if today.date() <= found.date() <= (today + timedelta(days=730)).date():
                return found
    return None


async def async_discover_events(hass) -> list[dict]:
    """Search public RSS results and return explicitly dated possible events."""
    session = async_get_clientsession(hass)
    today = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    seen = set()
    discovered = []

    async def fetch(query: str):
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(query)
            + "&hl=en-GB&gl=GB&ceid=GB:en"
        )
        try:
            async with asyncio.timeout(20):
                async with session.get(url, headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.1"}) as response:
                    if response.status != 200:
                        return []
                    body = await response.text()
            root = ET.fromstring(body)
        except (Exception, asyncio.TimeoutError):
            return []

        results = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            description = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            event_date = _find_future_date(f"{title} {description}", today)
            if event_date is None:
                continue
            key = link.split("&", 1)[0]
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "summary": f"Possible event: {title[:180]}",
                "start": event_date,
                "end": event_date + timedelta(days=1),
                "description": (
                    "Unverified discovery from Google News RSS. The date was "
                    "extracted from the result title/snippet and may need checking. "
                    f"Original result: {link}"
                ),
                "url": link,
                "category": "discovered-unverified",
            })
        return results

    batches = await asyncio.gather(*(fetch(query) for query in SEARCHES))
    for batch in batches:
        discovered.extend(batch)
    return sorted(discovered, key=lambda item: item["start"])
