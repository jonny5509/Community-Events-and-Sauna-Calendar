"""Best-effort discovery of publicly indexed, dated community events."""
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Google News country editions. Unknown country names still become a query term,
# while the RSS feed falls back to its English/global edition.
COUNTRY_CODES = {
    "australia": "AU", "austria": "AT", "belgium": "BE",
    "brazil": "BR", "canada": "CA", "denmark": "DK",
    "finland": "FI", "france": "FR", "germany": "DE",
    "india": "IN", "ireland": "IE", "italy": "IT",
    "japan": "JP", "mexico": "MX", "netherlands": "NL",
    "new zealand": "NZ", "norway": "NO", "portugal": "PT",
    "singapore": "SG", "south africa": "ZA", "south korea": "KR",
    "spain": "ES", "sweden": "SE", "switzerland": "CH",
    "united kingdom": "GB", "uk": "GB", "united states": "US",
    "usa": "US",
}
SEARCHES = (
    ("community", '"chastity" event'),
    ("community", '"Locktober" event'),
    ("community", '"male chastity" event'),
    ("community", '"chastity challenge" dates'),
    ("community", '"No Nut November" event'),
    ("community", '"kink event" chastity'),
    ("community", '"chastity" convention OR meetup OR contest'),
    ("pride", '"Pride" festival parade'),
    ("pride", '"LGBTQ" events festival'),
    ("pride", '"LGBTQIA" Pride events dates'),
    ("pride", '"Trans Pride" events'),
    ("pride", '"Bi Pride" OR "Lesbian Pride" events'),
    ("pride", '"Pride Month" events dates'),
    ("pride", '"LGBTQ History Month" events'),
    ("pride", '"Trans Day of Visibility" event'),
    ("pride", '"International Day Against Homophobia" event'),
    ("pride", '"Bi Visibility Day" event'),
    ("pride", '"Trans Day of Remembrance" event'),
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


async def async_discover_events(
    hass, country: str = "", location: str = ""
) -> list[dict]:
    """Search public RSS results, scoped to a country and optional local area."""
    session = async_get_clientsession(hass)
    today = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    country = (country or "").strip()
    location = (location or "").strip()
    country_code = COUNTRY_CODES.get(country.casefold(), "")
    # Put geographic terms directly in each query as well as selecting the
    # corresponding Google News edition. This is relevance filtering, not a
    # guarantee that every result physically takes place in that area.
    geographic_terms = " ".join(
        f'"{term}"' if " " in term else term
        for term in (country, location) if term
    )
    seen = set()
    discovered = []

    async def fetch(category: str, query: str):
        localized_query = f"{query} {geographic_terms}".strip()
        gl = country_code or "US"
        ceid = f"{gl}:en"
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(localized_query)
            + f"&hl=en-{gl}&gl={gl}&ceid={ceid}"
        )
        try:
            async with asyncio.timeout(20):
                async with session.get(
                    url,
                    headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.2"},
                ) as response:
                    if response.status != 200:
                        _LOGGER.warning(
                            "Google News RSS returned HTTP %s for query %r",
                            response.status,
                            localized_query,
                        )
                        return []
                    body = await response.text()
            root = ET.fromstring(body)
        except (Exception, asyncio.TimeoutError) as err:
            _LOGGER.warning(
                "Unable to fetch or parse Google News RSS for query %r: %s",
                localized_query,
                err,
            )
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
                    f"Search area: {', '.join(term for term in (location, country) if term) or 'not specified'}. "
                    "Search relevance does not guarantee the event is physically in this area. "
                    f"Original result: {link}"
                ),
                "url": link,
                "category": category,
            })
        return results

    batches = await asyncio.gather(*(fetch(category, query) for category, query in SEARCHES))
    for batch in batches:
        discovered.extend(batch)
    return sorted(discovered, key=lambda item: item["start"])
