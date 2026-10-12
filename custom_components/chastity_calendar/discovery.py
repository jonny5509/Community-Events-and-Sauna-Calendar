"""Best-effort multi-source discovery of public, dated community events."""
from __future__ import annotations
import asyncio
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit
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

_COUNTRY_CODE_CACHE: dict[str, str] = {}


async def _country_code(session, country: str) -> str:
    """Resolve ISO country codes for countries outside the built-in aliases."""
    normalized = (country or "").strip().casefold()
    if not normalized:
        return ""
    if normalized in COUNTRY_CODES:
        return COUNTRY_CODES[normalized]
    if normalized in _COUNTRY_CODE_CACHE:
        return _COUNTRY_CODE_CACHE[normalized]
    try:
        url = f"https://restcountries.com/v3.1/name/{quote(country.strip(), safe='')}?fields=cca2"
        async with asyncio.timeout(8):
            async with session.get(url, headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.6"}) as response:
                if response.status != 200:
                    return ""
                payload = await response.json()
        code = next(
            (item.get("cca2", "") for item in payload if isinstance(item, dict) and item.get("cca2")),
            "",
        ) if isinstance(payload, list) else ""
        code = str(code).upper()
        if len(code) == 2:
            _COUNTRY_CODE_CACHE[normalized] = code
            return code
    except Exception as err:
        _LOGGER.debug("Could not resolve ISO country code for %r: %s", country, err)
    return ""

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
    url = "https://news.google.com/rss/search?q=" + quote_plus(localized)
    if country_code:
        url += f"&hl=en-{country_code}&gl={country_code}&ceid={country_code}:en"
    else:
        # Never silently force searches for unsupported countries into US locale.
        url += "&hl=en"
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
            raw = item.get("dates",{}).get("start",{}).get("localDate") or item.get("dates",{}).get("start",{}).get("dateTime")
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
    """Merge duplicate title/date matches without collapsing a venue's event list."""
    merged = {}
    title_date_to_key = {}
    for event in events:
        title_key = re.sub(r"[^a-z0-9]+", " ", event["summary"].casefold()).strip()
        date_key = event["start"].date().isoformat()
        # A venue page is often the URL for every event on that venue's website.
        # URL-only merging therefore loses distinct event names and dates,
        # especially when several JSON-LD events fall back to the same page URL.
        # Treat the same title on the same date as a duplicate instead.
        identity = (title_key, date_key)
        key = title_date_to_key.get(identity)
        if key is None:
            key = ("event", len(merged))
            merged[key] = event
        else:
            old = merged[key]
            if event.get("date_confidence") == "structured" or old.get("date_confidence") != "structured":
                old["start"], old["end"] = event["start"], event["end"]
            old["categories"] = sorted(set(old.get("categories", [])) | set(event.get("categories", [])))
            old["sources"] = sorted(set(old.get("sources", [])) | set(event.get("sources", [])))
            old["source_links"] = list(dict.fromkeys(old.get("source_links", []) + event.get("source_links", [])))
            if event.get("location") and not old.get("location"):
                old["location"] = event["location"]
            if event.get("date_confidence") == "structured":
                old["summary"], old["url"], old["description"] = event["summary"], event["url"], event["description"]
                old["date_confidence"] = "structured"
        title_date_to_key[identity] = key
    return sorted(merged.values(), key=lambda item: item["start"])


async def _jsonld_event_records(session, website: str, venue_name: str, venue_location: str, today: datetime):
    """Extract future Event records from a venue website's Schema.org JSON-LD."""
    try:
        async with asyncio.timeout(12):
            async with session.get(
                website,
                headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.6 (public event discovery)"},
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    return []
                content_type = response.headers.get("Content-Type", "").casefold()
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return []
                body = await response.text(errors="ignore")
    except Exception as err:
        _LOGGER.debug("Could not fetch sauna website %s: %s", website, err)
        return []

    scripts = re.findall(
        r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script\s*>",
        body,
        flags=re.I | re.S,
    )
    found = []

    def walk(value):
        if isinstance(value, list):
            for child in value:
                yield from walk(child)
        elif isinstance(value, dict):
            kind = value.get("@type", [])
            kinds = {kind.casefold()} if isinstance(kind, str) else {
                str(item).casefold() for item in kind
            } if isinstance(kind, list) else set()
            if "event" in kinds or any(item.endswith("event") for item in kinds):
                yield value
            for key, child in value.items():
                if key in {"@graph", "mainEntity", "event"}:
                    yield from walk(child)

    for script in scripts:
        try:
            payload = json.loads(html.unescape(script).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        for item in walk(payload):
            title = str(item.get("name") or "").strip()
            raw_start = item.get("startDate")
            if not title or not raw_start:
                continue
            try:
                start = datetime.fromisoformat(str(raw_start).replace("Z", "+00:00"))
                if start.tzinfo is not None:
                    start = start.replace(tzinfo=None)
            except ValueError:
                continue
            if not today.date() <= start.date() <= (today + timedelta(days=730)).date():
                continue
            raw_end = item.get("endDate")
            end = start + timedelta(days=1)
            if raw_end:
                try:
                    parsed_end = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00"))
                    if parsed_end.tzinfo is not None:
                        parsed_end = parsed_end.replace(tzinfo=None)
                    # Home Assistant all-day calendar events use an exclusive end date.
                    end = max(start + timedelta(days=1), parsed_end)
                except ValueError:
                    pass
            description = str(item.get("description") or "").strip()
            event_url = str(item.get("url") or website).strip()
            record = _record(
                title, start, event_url, "sauna",
                f"Found in Schema.org Event data published by {venue_name}. "
                f"Venue: {venue_location or venue_name}. "
                "Automatically collected from the venue website; confirm details with the organiser. "
                f"{description}",
                source=f"Sauna website: {venue_name}",
                location=venue_location or venue_name,
            )
            record["end"] = end
            record["date_confidence"] = "structured"
            found.append(record)
    return found


async def _fetch_nearby_sauna_website_events(session, country: str, location: str, today: datetime):
    """Find nearby OSM sauna websites and read their structured event listings."""
    query = ", ".join(part for part in (location, country) if part)
    if not query:
        return []
    headers = {"User-Agent": "HomeAssistant-ChastityCalendar/1.6 (OpenStreetMap sauna event discovery)"}
    try:
        async with asyncio.timeout(12):
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "jsonv2", "limit": "1"},
                headers=headers,
            ) as response:
                response.raise_for_status()
                geocoded = await response.json()
        if not geocoded:
            return []
        lat, lon = float(geocoded[0]["lat"]), float(geocoded[0]["lon"])
        overpass_query = f"""[out:json][timeout:20];
(
  nwr(around:20000,{lat},{lon})[leisure=sauna][website];
  nwr(around:20000,{lat},{lon})[leisure=sauna]["contact:website"];
  nwr(around:20000,{lat},{lon})[amenity=sauna][website];
  nwr(around:20000,{lat},{lon})[amenity=sauna]["contact:website"];
  nwr(around:20000,{lat},{lon})[amenity=public_bath][website];
  nwr(around:20000,{lat},{lon})[amenity=public_bath]["contact:website"];
  nwr(around:20000,{lat},{lon})[sauna=yes][website];
  nwr(around:20000,{lat},{lon})[sauna=yes]["contact:website"];
);
out center tags;"""
        payload = None
        for endpoint in (
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
        ):
            try:
                async with asyncio.timeout(25):
                    async with session.post(
                        endpoint, data=overpass_query, headers=headers
                    ) as response:
                        response.raise_for_status()
                        payload = await response.json()
                break
            except Exception as err:
                _LOGGER.debug("Overpass endpoint %s failed during sauna event lookup: %s", endpoint, err)
        if payload is None:
            return []
    except Exception as err:
        _LOGGER.debug("Could not find nearby sauna websites: %s", err)
        return []

    venues = []
    seen = set()
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        website = tags.get("website") or tags.get("contact:website")
        name = tags.get("name") or tags.get("name:en")
        if not website or not name:
            continue
        if not website.startswith(("https://", "http://")):
            website = "https://" + website
        if website in seen:
            continue
        seen.add(website)
        address = ", ".join(part for part in (
            tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:suburb"),
            tags.get("addr:country"),
        ) if part)
        venues.append((website, name, address or name))

    # Keep load on small venue websites modest and avoid scraping every mapped result.
    venues = venues[:12]
    batches = await asyncio.gather(*(
        _jsonld_event_records(session, website, name, address, today)
        for website, name, address in venues
    ))
    return [event for batch in batches for event in batch]

async def async_discover_events(hass, country: str = "", location: str = "", ticketmaster_api_key: str = "") -> list[dict]:
    """Search public sources for dated events in the configured country."""
    session = async_get_clientsession(hass)
    today = dt_util.now().replace(hour=0,minute=0,second=0,microsecond=0)
    country = (country or "").strip()
    location = (location or "").strip()
    code = await _country_code(session, country)
    searches = list(SEARCHES)
    for year in (today.year,today.year+1):
        searches.extend([("community",f'"community festival" {year} schedule dates'),
                         ("community",f'convention OR expo OR festival {year} dates'),
                         ("pride",f'"Pride festival" {year} dates')])
    rss = await asyncio.gather(*(_fetch_rss(session,cat,q,country,location,code,today) for cat,q in searches))
    events = [item for batch in rss for item in batch]
    events.extend(await _fetch_ticketmaster(session,(ticketmaster_api_key or "").strip(),code,today))
    events.extend(await _fetch_nearby_sauna_website_events(session, country, location, today))
    # Repeated source URLs collapse even when the publisher has changed the date;
    # matching titles/dates from separate sources are merged where possible.
    return _deduplicate(events)
