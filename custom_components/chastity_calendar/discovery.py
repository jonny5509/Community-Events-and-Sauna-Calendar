"""Best-effort multi-source discovery of public, dated community events."""
from __future__ import annotations
import asyncio
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlsplit, urlunsplit
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)
COUNTRY_CODES = {
    "australia":"AU","austria":"AT","belgium":"BE","brazil":"BR","canada":"CA",
    "denmark":"DK","finland":"FI","france":"FR","germany":"DE","india":"IN",
    "ireland":"IE","italy":"IT","japan":"JP","mexico":"MX","netherlands":"NL",
    "new zealand":"NZ","norway":"NO","portugal":"PT","singapore":"SG",
    "south africa":"ZA","south korea":"KR","spain":"ES","sweden":"SE",
    "switzerland":"CH","united kingdom":"GB","uk":"GB","united states":"US","usa":"US",
}
SEARCHES = (
    ("community", '"community events" festival meetup dates'),
    ("community", '"community festival" OR "community fair" events'),
    ("community", 'convention OR expo OR conference events dates'),
    ("community", 'workshop OR meetup OR social event schedule'),
    ("community", 'music festival OR arts festival events dates'),
    ("community", 'food festival OR street festival dates'),
    ("kink", '"kink event" OR "BDSM event" dates'),
    ("kink", '"fetish night" OR "fetish festival" dates'),
    ("chastity", '"chastity" event OR meetup OR convention dates'),
    ("chastity", '"Locktober" OR "male chastity" challenge events'),
    ("adult", '"adults only" event OR party OR festival dates'),
    ("adult", '"18+" fetish event OR adult social dates'),
    ("pride", 'LGBTQ OR LGBTQIA Pride festival parade events dates'),
    ("gay", '"gay men" OR "gay pride" festival meetup dates'),
    ("lesbian", 'lesbian festival OR meetup OR pride events dates'),
    ("bisexual", 'bisexual OR "bi pride" community events dates'),
    ("transgender", '"trans pride" OR transgender community events dates'),
    ("queer", 'queer LGBTQ festival OR community event dates'),
    ("lgbtq", 'LGBTQ events nightlife social festival dates'),
)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
RANGE_PATTERN = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*[-–—]\s*(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b", re.I)
DATE_PATTERNS = (
    re.compile(rf"\b({MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b", re.I),
    re.compile(rf"\b(\d{{1,2}})\s+({MONTHS})[,]?\s+(20\d{{2}})\b", re.I),
    re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),
)

def _find_future_date(text: str, today: datetime):
    """Extract the earliest explicit date within the next two years."""
    found_dates = []
    for m in RANGE_PATTERN.finditer(text):
        try: found_dates.append(datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(4)}", "%B %d %Y"))
        except ValueError: pass
    for index, pattern in enumerate(DATE_PATTERNS):
        for m in pattern.finditer(text):
            try:
                if index == 0: value = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y")
                elif index == 1: value = datetime.strptime(f"{m.group(2)} {m.group(1)} {m.group(3)}", "%B %d %Y")
                else: value = datetime.strptime(m.group(0), "%Y-%m-%d")
                found_dates.append(value)
            except ValueError: pass
    eligible = [d for d in found_dates if today.date() <= d.date() <= (today + timedelta(days=730)).date()]
    return min(eligible, key=lambda d: d.date()) if eligible else None

def _normalise_url(url: str) -> str:
    """Strip tracking parameters to improve duplicate detection."""
    try:
        p = urlsplit(url.strip())
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))
    except ValueError: return url.strip()

def _category_tags(category: str, title: str, description: str) -> list[str]:
    """Return overlapping keyword-based category tags."""
    text = f"{category} {title} {description}".casefold()
    rules = {
        "community": ("community","meetup","workshop","conference","convention","social","expo"),
        "lgbtq": ("lgbt","queer","pride","gay","lesbian","bisexual","transgender"),
        "gay": ("gay",), "lesbian": ("lesbian",), "bisexual": ("bisexual","bi pride"),
        "transgender": ("transgender","trans pride"), "queer": ("queer",), "pride": ("pride",),
        "kink": ("kink","bdsm","fetish","leather","puppy play"),
        "chastity": ("chastity","locktober","no nut november"),
        "adult": ("adult-only","adults only","18+","fetish","bdsm","erotic"),
        "festival": ("festival","parade","fair","carnival"),
        "arts_music": ("music","concert","arts","theatre","theater","gallery"),
    }
    tags = {category}
    tags.update(tag for tag, words in rules.items() if any(word in text for word in words))
    return sorted(tags)

def _record(title, start, url, category, description, source="Google News RSS", location=""):
    """Create a consistent discovery record."""
    title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
    description = html.unescape(re.sub(r"<[^>]+>", "", description)).strip()
    return {
        "summary": title[:180] or "Possible event",
        "start": start, "end": start + timedelta(days=1),
        "description": description[:1200], "url": url, "category": category,
        "categories": _category_tags(category, title, description),
        "location": location, "source": source, "sources": [source],
        "source_links": [url] if url else [], "last_seen": dt_util.now().isoformat(),
        "date_confidence": "extracted_from_search_snippet",
    }

async def _fetch_rss(session, category, query, country, location, country_code, today):
    """Fetch one public Google News RSS search."""
    terms = " ".join(f'"{x}"' if " " in x else x for x in (country, location) if x)
    localized = f"{query} {terms}".strip()
    gl = country_code or "US"
    url = "https://news.google.com/rss/search?q=" + quote_plus(localized) + f"&hl=en-{gl}&gl={gl}&ceid={gl}:en"
    try:
        async with asyncio.timeout(20):
            async with session.get(url, headers={"User-Agent":"HomeAssistant-ChastityCalendar/1.4"}) as response:
                if response.status != 200:
                    _LOGGER.debug("Google News RSS HTTP %s for %r", response.status, localized)
                    return []
                body = await response.text()
        root = ET.fromstring(body)
    except Exception as err:
        _LOGGER.debug("Google News RSS failed for %r: %s", localized, err)
        return []
    results = []
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        description = item.findtext("description") or ""
        link = item.findtext("link") or ""
        if not title.strip() or not link.strip(): continue
        event_date = _find_future_date(f"{title} {description}", today)
        if event_date is None: continue
        title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
        results.append(_record(
            title, event_date, link, category,
            "Unverified public search result. Date extracted from title/snippet and may be wrong. "
            f"Configured country: {country or 'not set'}. Search relevance is not proof of venue location. "
            f"Verify details with the original listing: {link}",
        ))
    return results

async def _fetch_ticketmaster(session, api_key, country_code, today):
    """Search Ticketmaster's structured event catalogue when an API key is configured."""
    if not api_key or not country_code: return []
    terms = ("LGBTQ Pride","community festival","community event","convention","kink fetish",
             "chastity","adult only","gay lesbian queer","music arts festival","workshop meetup")
    async def fetch_term(term):
        params = {"apikey":api_key,"countryCode":country_code,"keyword":term,"size":"100","page":"0","sort":"date,asc"}
        try:
            async with asyncio.timeout(20):
                async with session.get("https://app.ticketmaster.com/discovery/v2/events.json",params=params) as response:
                    if response.status != 200:
                        _LOGGER.warning("Ticketmaster API HTTP %s; check the optional API key.",response.status)
                        return []
                    payload = await response.json(content_type=None)
        except Exception as err:
            _LOGGER.debug("Ticketmaster search failed for %r: %s",term,err)
            return []
        records = []
        for item in payload.get("_embedded",{}).get("events",[]):
            raw = item.get("dates",{}).get("start",{}).get("dateTime") or item.get("dates",{}).get("start",{}).get("localDate")
            if not raw: continue
            try: start = datetime.fromisoformat(raw.replace("Z","+00:00")).replace(tzinfo=None)
            except ValueError: continue
            if not today.date() <= start.date() <= (today + timedelta(days=730)).date(): continue
            venues = item.get("_embedded",{}).get("venues",[])
            venue = venues[0] if venues else {}
            location = ", ".join(filter(None,(venue.get("name"),venue.get("city",{}).get("name"),venue.get("state",{}).get("name"),venue.get("country",{}).get("name"))))
            title = item.get("name","Unnamed event")
            text = f"{term} {title}".casefold()
            category = next((cat for word,cat in (("chastity","chastity"),("fetish","kink"),("kink","kink"),("adult","adult"),("trans","transgender"),("lesbian","lesbian"),("bisexual","bisexual"),("gay","gay"),("queer","queer"),("pride","pride"),("lgbt","lgbtq")) if word in text),"community")
            records.append(_record(title,start,item.get("url",""),category,
                f"Structured listing from Ticketmaster Discovery API. Verify event details with the organiser. Venue: {location or 'not supplied'}.",
                source="Ticketmaster Discovery API",location=location))
            records[-1]["date_confidence"] = "structured"
        return records
    batches = await asyncio.gather(*(fetch_term(term) for term in terms))
    return [item for batch in batches for item in batch]

def _deduplicate(events):
    """Merge repeated URLs and cross-source title/date duplicates."""
    merged = {}
    for event in events:
        url_key = _normalise_url(event.get("url",""))
        title_key = re.sub(r"[^a-z0-9]+"," ",event["summary"].casefold()).strip()
        key = ("url",url_key) if url_key else ("title-date",title_key,event["start"].date().isoformat())
        if key not in merged:
            merged[key] = event
            continue
        old = merged[key]
        if event.get("date_confidence") == "structured" or old.get("date_confidence") != "structured":
            old["start"],old["end"] = event["start"],event["end"]
        old["categories"] = sorted(set(old.get("categories",[])) | set(event.get("categories",[])))
        old["sources"] = sorted(set(old.get("sources",[])) | set(event.get("sources",[])))
        old["source_links"] = list(dict.fromkeys(old.get("source_links",[]) + event.get("source_links",[])))
        if event.get("location") and not old.get("location"): old["location"] = event["location"]
        if event.get("date_confidence") == "structured":
            old["summary"],old["url"],old["description"] = event["summary"],event["url"],event["description"]
            old["date_confidence"] = "structured"
    return sorted(merged.values(),key=lambda item:item["start"])

async def async_discover_events(hass, country: str = "", location: str = "", ticketmaster_api_key: str = "") -> list[dict]:
    """Search public sources for dated events in the configured country."""
    session = async_get_clientsession(hass)
    today = dt_util.now().replace(hour=0,minute=0,second=0,microsecond=0)
    country = (country or "").strip()
    location = (location or "").strip()
    code = COUNTRY_CODES.get(country.casefold(),"")
    searches = list(SEARCHES)
    for year in (today.year,today.year+1):
        searches.extend([("community",f'"community festival" {year} schedule dates'),
                         ("community",f'convention OR expo OR festival {year} dates'),
                         ("pride",f'"Pride festival" {year} dates')])
    rss = await asyncio.gather(*(_fetch_rss(session,cat,q,country,location,code,today) for cat,q in searches))
    events = [item for batch in rss for item in batch]
    events.extend(await _fetch_ticketmaster(session,(ticketmaster_api_key or "").strip(),code,today))
    # Repeated source URLs collapse even when the publisher has changed the date;
    # matching titles/dates from separate sources are merged where possible.
    return _deduplicate(events)
