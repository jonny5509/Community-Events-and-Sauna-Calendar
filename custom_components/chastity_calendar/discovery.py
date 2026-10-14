"""Best-effort multi-source discovery of public, dated community events."""
from __future__ import annotations
import asyncio
import calendar as _calendar
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
    ("kink", '"leather event" OR "leather weekend" fetish dates'),
    ("kink", '"rubber" OR "latex" fetish event party dates'),
    ("kink", '"BDSM workshop" OR "rope workshop" OR shibari event dates'),
    ("kink", '"pup play" OR "pet play" kink meetup event dates'),
    ("kink", '"fetish convention" OR "fetish market" OR "gear social" dates'),
    ("kink", '"foot fetish" OR boot fetish community event dates'),
    ("kink", '"power exchange" OR "dominance submission" workshop event dates'),
    ("kink", '"findom" OR "financial domination" community event dates'),
    ("kink", '"furry meetup" OR "furry convention" events dates'),
    ("kink", '"fetish fashion" OR latex fashion event dates'),
    ("kink", '"International Fetish Day" OR "World BDSM Day" dates'),
    ("kink", '"straight kink" OR heterosexual BDSM OR "straight fetish" events dates'),
    ("kink", '"straight couples" BDSM OR fetish night meetup dates'),
    ("gay", '"gay BDSM" OR "gay kink" OR "gay fetish" event dates'),
    ("gay", '"gay leather" OR "gay rubber" OR "gay pup play" event dates'),
    ("gay", '"gay male" bondage OR chastity OR gear social dates'),
    ("lesbian", '"lesbian BDSM" OR "lesbian kink" OR "lesbian fetish" event dates'),
    ("lesbian", '"sapphic kink" OR "queer women" fetish meetup dates'),
    ("bisexual", '"bisexual kink" OR "bi BDSM" OR "bi fetish" events dates'),
    ("transgender", '"trans kink" OR "trans BDSM" OR transgender fetish community events dates'),
    ("queer", '"queer kink" OR "queer BDSM" OR "queer fetish" event dates'),
    ("kink", '"women in kink" OR "female dominatrix" workshop event dates'),
    ("kink", '"men in kink" OR "male dominance" BDSM event dates'),
    ("kink", '"couples BDSM" OR "couples fetish" workshop social dates'),
    ("kink", '"dominatrix" OR "professional domination" community event dates'),
    ("kink", '"crossdressing" OR "sissy" fetish social event dates'),
    ("kink", '"corsetry" OR "high heels" OR "stocking fetish" event dates'),
    ("kink", '"sensory play" OR "impact play" OR bondage workshop events dates'),
    ("kink", '"medical fetish" OR "uniform fetish" OR "roleplay kink" events dates'),
    ("kink", '"watersports fetish" OR "food play" OR "sploshing" event dates'),
    ("kink", '"wax play" OR "sensory deprivation" kink workshop dates'),
    ("kink", '"consensual non-monogamy" OR polyamory kink social event dates'),
    ("chastity", '"chastity" event OR meetup OR convention dates'),
    ("chastity", '"Locktober" OR "male chastity" challenge events'),
    ("adult", '"adults only" event OR party OR festival dates'),
    ("adult", '"18+" fetish event OR adult social dates'),
    ("pride", 'LGBTQ OR LGBTQIA Pride festival parade events dates'),
    ("gay", '"gay men" OR "gay pride" festival meetup dates'),
    ("gay", '"gay events" calendar social dates'),
    ("gay", '"gay men" social event festival 2026 OR 2027'),
    ("gay", '"gay community" event calendar meetup'),
    ("lesbian", 'lesbian festival OR meetup OR pride events dates'),
    ("bisexual", 'bisexual OR "bi pride" community events dates'),
    ("transgender", '"trans pride" OR transgender community events dates'),
    ("queer", 'queer LGBTQ festival OR community event dates'),
    ("sauna", '"gay sauna" events calendar dates'),
    ("sauna", '"sauna event" OR "sauna theme night" dates'),
    ("sauna", '"gay sauna" themed nights events 2026 OR 2027'),
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
    """Extract the earliest explicit or yearless event date in the next two years.

    Search snippets often show dates such as "Friday 16 October" without a
    year. Treat those as the next occurrence, rather than dropping the event.
    Numeric dates use UK-style day/month/year; ISO dates remain unambiguous.
    """
    found_dates = []
    month_names = "January|February|March|April|May|June|July|August|September|October|November|December"
    month_abbrevs = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    patterns = (
        re.compile(rf"\b({month_names}|{month_abbrevs})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s*(20\d{{2}})?\b", re.I),
        re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names}|{month_abbrevs})\.?[,]?\s*(20\d{{2}})?\b", re.I),
        re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d{2}|\d{2})\b"),
        re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),
    )
    for pattern_index, pattern in enumerate(patterns):
        for match in pattern.finditer(text):
            try:
                if pattern_index == 0:
                    month_text, day_text, year_text = match.groups()
                    month_day = f"{month_text.rstrip('.')} {day_text}"
                elif pattern_index == 1:
                    day_text, month_text, year_text = match.groups()
                    month_day = f"{month_text.rstrip('.')} {day_text}"
                elif pattern_index == 2:
                    day_text, month_text, year_text = match.groups()
                    year_text = ("20" + year_text) if len(year_text) == 2 else year_text
                    found_dates.append(datetime(int(year_text), int(month_text), int(day_text)))
                    continue
                else:
                    year_text, month_text, day_text = match.groups()
                    found_dates.append(datetime(int(year_text), int(month_text), int(day_text)))
                    continue

                if year_text:
                    parsed_month_day = None
                    for fmt in ("%B %d", "%b %d"):
                        try:
                            parsed_month_day = datetime.strptime(month_day, fmt)
                            break
                        except ValueError:
                            continue
                    if parsed_month_day is None:
                        continue
                    found_dates.append(datetime(int(year_text), parsed_month_day.month, parsed_month_day.day))
                else:
                    parsed_month_day = None
                    for fmt in ("%B %d", "%b %d"):
                        try:
                            parsed_month_day = datetime.strptime(month_day, fmt)
                            break
                        except ValueError:
                            continue
                    if parsed_month_day is None:
                        continue
                    for year in (today.year, today.year + 1, today.year + 2):
                        try:
                            found_dates.append(datetime(year, parsed_month_day.month, parsed_month_day.day))
                        except ValueError:
                            pass
            except (ValueError, TypeError):
                continue

    for match in RANGE_PATTERN.finditer(text):
        try:
            found_dates.append(datetime.strptime(
                f"{match.group(1)} {match.group(2)} {match.group(4)}", "%B %d %Y"
            ))
        except ValueError:
            pass

    lower = today.date()
    upper = (today + timedelta(days=730)).date()
    eligible = [value for value in found_dates if lower <= value.date() <= upper]
    return min(eligible, key=lambda value: value.date()) if eligible else None

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
        "lgbtq": ("lgbt","queer","pride","gay","lesbian","bisexual","transgender","sapphic"),
        "gay": ("gay",), "lesbian": ("lesbian","sapphic"), "bisexual": ("bisexual","bi pride"),
        "transgender": ("transgender","trans pride","trans kink"), "queer": ("queer",), "pride": ("pride",),
        "straight": ("straight kink","straight couples","heterosexual bdsm","straight fetish"),
        "kink": ("kink","bdsm","fetish","leather","puppy play","pup play","pet play","rubber","latex","shibari","rope bondage","findom","financial domination","foot fetish","gear social","power exchange","dominance and submission","fetish fashion","furry"),
        "chastity": ("chastity","locktober","no nut november"),
        "adult": ("adult-only","adults only","18+","fetish","bdsm","erotic","kink event","fetish night","leather event","rubber event"),
        "sauna": ("sauna","steam room","number 52 sauna"),
        "festival": ("festival","parade","fair","carnival"),
        "arts_music": ("music","concert","arts","theatre","theater","gallery"),
    }
    tags = {category}
    tags.update(tag for tag, words in rules.items() if any(word in text for word in words))
    return sorted(tags)

def _record(title, start, url, category, description, source="Google News RSS", location="", date_confidence="extracted_from_search_snippet"):
    """Create a consistent discovery record."""
    title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
    description = html.unescape(re.sub(r"<[^>]+>", "", description)).strip()
    # A sauna search query is not evidence that every returned article is a
    # sauna event. Require explicit venue/topic context before routing it to
    # the dedicated sauna calendar.
    sauna_context = re.search(
        r"\bsaunas?\b|\bsteam room\b|\bnumber\s*52\b",
        f"{title} {description} {url} {location}",
        re.IGNORECASE,
    )
    record_category = (
        "sauna" if category == "sauna" and sauna_context
        else "community" if category == "sauna"
        else category
    )
    return {
        "summary": title[:180] or "Possible event",
        "start": start, "end": start + timedelta(days=1),
        "description": description[:1200], "url": url, "category": record_category,
        "categories": _category_tags(record_category, title, description),
        "location": location, "source": source, "sources": [source],
        "source_links": [url] if url else [], "last_seen": dt_util.now().isoformat(),
        "date_confidence": date_confidence,
    }


async def _fetch_structured_event_date(session, url: str, today: datetime):
    """Extract an explicit event start date from a public event page."""
    if urlsplit(url).scheme not in {"http", "https"}:
        return None
    try:
        async with asyncio.timeout(6):
            async with session.get(
                url,
                headers={"User-Agent": "HomeAssistant-CommunityEventsCalendar/2.0.3"},
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    return None
                body = (await response.text())[:1500000]
    except Exception as err:
        _LOGGER.debug("Could not inspect event page %s: %s", url, err)
        return None

    raw_dates = []
    script_pattern = re.compile(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script\s*>', re.I | re.S)
    for raw in script_pattern.findall(body):
        try:
            payload = json.loads(html.unescape(raw))
        except (ValueError, TypeError):
            continue
        stack = [payload]
        while stack:
            value = stack.pop()
            if isinstance(value, list):
                stack.extend(value)
            elif isinstance(value, dict):
                types = value.get("@type", [])
                if isinstance(types, str):
                    types = [types]
                if any(str(kind).casefold() == "event" for kind in types):
                    start_date = value.get("startDate")
                    if isinstance(start_date, str):
                        raw_dates.append(start_date)
                stack.extend(item for key, item in value.items() if key not in {"@context", "startDate"})
    meta_pattern = re.compile(r'<meta[^>]+(?:property|name)=["\']event:start_time["\'][^>]+content=["\']([^"\']+)', re.I)
    raw_dates.extend(meta_pattern.findall(body))
    candidates = []
    for raw in raw_dates:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            parsed = _find_future_date(str(raw), today)
        if parsed and today.date() <= parsed.date() <= (today + timedelta(days=730)).date():
            candidates.append(parsed)
    return min(candidates, key=lambda item: item.date()) if candidates else None

async def _fetch_rss(session, category, query, country, location, country_code, today, search_location=None):
    """Fetch one public Google News RSS search."""
    # Prefer the specific geographic level for this query, while always retaining country context.
    terms = " ".join(f'"{x}"' if " " in x else x for x in (country, search_location or location) if x)
    localized = f"{query} {terms}".strip()
    url = "https://news.google.com/rss/search?q=" + quote_plus(localized)
    if country_code:
        url += f"&hl=en-{country_code}&gl={country_code}&ceid={country_code}:en"
    else:
        # Never silently force searches for unsupported countries into US locale.
        url += "&hl=en"
    try:
        async with asyncio.timeout(8):
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
    structured_date_checks = 0
    lgbtq_categories = {"pride", "gay", "lesbian", "bisexual", "transgender", "queer", "lgbtq"}
    structured_date_categories = lgbtq_categories | {"kink", "chastity", "adult"}
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        description = item.findtext("description") or ""
        link = item.findtext("link") or ""
        if not title.strip() or not link.strip(): continue
        event_date = _find_future_date(f"{title} {description}", today)
        # Search snippets often omit dates. Inspect a bounded number of LGBTQ+,
        # kink/fetish, chastity, and adult-event pages for explicit structured
        # Event.startDate metadata; never substitute an article publication date.
        date_confidence = "extracted_from_search_snippet"
        max_structured_checks = 8 if category in lgbtq_categories else 4
        if (event_date is None and category in structured_date_categories
                and structured_date_checks < max_structured_checks):
            structured_date_checks += 1
            event_date = await _fetch_structured_event_date(session, link, today)
            if event_date is not None:
                date_confidence = "extracted_from_event_page"
        if event_date is None:
            continue
        title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
        results.append(_record(
            title, event_date, link, category,
            "Unverified public search result. Date extracted from title/snippet and may be wrong. "
            f"Configured country: {country or 'not set'}. Search relevance is not proof of venue location. "
            f"Verify details with the original listing: {link}",
            date_confidence=date_confidence,
        ))
    return results

async def _fetch_ticketmaster(session, api_key, country_code, today, coordinates=None, radius_km=30):
    """Search Ticketmaster's structured catalogue within the configured radius when possible."""
    if not api_key or not country_code: return []
    terms = ("LGBTQ Pride","gay events","gay men social","gay pride festival","community festival","community event","convention","kink fetish",
             "chastity","adult only","gay lesbian queer","music arts festival","workshop meetup",
             "leather fetish","rubber latex","BDSM workshop","rope shibari","pup play","fetish convention","kink social")
    async def fetch_term(term):
        params = {"apikey":api_key,"countryCode":country_code,"keyword":term,"size":"100","page":"0","sort":"date,asc"}
        if coordinates:
            params["latlong"] = f"{coordinates[0]},{coordinates[1]}"
            params["radius"] = str(radius_km)
            params["unit"] = "km"
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



def _is_sauna_event(event: dict) -> bool:
    """Return whether event metadata explicitly identifies a sauna listing."""
    searchable = [
        event.get("summary", ""),
        event.get("description", ""),
        event.get("category", ""),
        event.get("url", ""),
        event.get("source", ""),
        *event.get("categories", []),
        *event.get("sources", []),
    ]
    return any(re.search(r"\bsaunas?\b", str(value), re.IGNORECASE) for value in searchable)


def _add_months(value: datetime, months: int) -> datetime:
    """Add calendar months without overflowing short months."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


async def _geocode_location(session, location: str, country: str):
    """Resolve configured town/area to coordinates using public Nominatim geocoding."""
    query = ", ".join(part for part in (location, country) if part)
    if not query:
        return None
    try:
        async with asyncio.timeout(10):
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "jsonv2", "limit": "1"},
                headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.6 (event discovery)"},
            ) as response:
                if response.status != 200:
                    return None
                results = await response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as err:
        _LOGGER.debug("Could not geocode configured event location %r: %s", query, err)
    return None


async def _fetch_sauna52_events(session, today: datetime) -> list[dict]:
    """Read dated and recurring events from Number 52 Sauna's own public pages."""
    base_url = "https://www.number52sauna.co.uk"
    # The main calendar and individual repeating-event pages are both checked.
    # The latter often expose dated instances in Schema.org JSON-LD even when
    # the JavaScript calendar itself is not rendered by Home Assistant.
    page_urls = (
        f"{base_url}/our-events/",
        f"{base_url}/our-offers/",
        f"{base_url}/event/fetish-night/var/ri-2.l-L1/",
        f"{base_url}/event/sports-chav-night/var/ri-2.l-L1/",
        f"{base_url}/event/dare-to-bare/var/ri-2.l-L1/",
        f"{base_url}/event/blackout/var/ri-2.l-L1/",
        f"{base_url}/event/top-vers-bottom-night/var/ri-2.l-L1/",
        f"{base_url}/event/jocks-n-cocks/var/ri-2.l-L1/",
    )

    async def fetch_page(url: str) -> tuple[str, str]:
        try:
            async with asyncio.timeout(12):
                async with session.get(
                    url,
                    headers={"User-Agent": "HomeAssistant-CommunityEventsCalendar/2.0.1"},
                ) as response:
                    if response.status != 200:
                        _LOGGER.debug("Number 52 page returned HTTP %s: %s", response.status, url)
                        return url, ""
                    return url, await response.text()
        except Exception as err:
            _LOGGER.debug("Could not fetch Number 52 page %s: %s", url, err)
            return url, ""

    pages = await asyncio.gather(*(fetch_page(url) for url in page_urls))
    events: list[dict] = []
    cutoff = today + timedelta(days=730)

    def walk_jsonld(value):
        """Yield Event objects from JSON-LD graphs and nested arrays."""
        if isinstance(value, list):
            for item in value:
                yield from walk_jsonld(item)
        elif isinstance(value, dict):
            types = value.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if any(str(item).casefold() == "event" for item in types):
                yield value
            for key, item in value.items():
                if key != "@context":
                    yield from walk_jsonld(item)

    for page_url, body in pages:
        if not body:
            continue
        for raw in re.findall(
            r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script\s*>',
            body,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            try:
                payload = json.loads(html.unescape(raw).strip())
            except (json.JSONDecodeError, TypeError):
                continue
            for item in walk_jsonld(payload):
                raw_start = item.get("startDate")
                if not isinstance(raw_start, str):
                    continue
                try:
                    start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    continue
                if not today.date() <= start.date() <= cutoff.date():
                    continue
                title = str(item.get("name") or "Number 52 Sauna event").strip()
                if not title:
                    continue
                raw_end = item.get("endDate")
                try:
                    end = datetime.fromisoformat(raw_end.replace("Z", "+00:00")).replace(tzinfo=None) if isinstance(raw_end, str) else start + timedelta(hours=2)
                except ValueError:
                    end = start + timedelta(hours=2)
                location_data = item.get("location", {})
                if isinstance(location_data, dict):
                    address = location_data.get("address", {})
                    if isinstance(address, dict):
                        location = ", ".join(
                            str(address.get(key, "")).strip()
                            for key in ("streetAddress", "addressLocality", "addressRegion", "addressCountry")
                            if address.get(key)
                        )
                    else:
                        location = str(address or "")
                    location = location or str(location_data.get("name") or "Number 52 Sauna, Newcastle upon Tyne")
                else:
                    location = "Number 52 Sauna, Newcastle upon Tyne"
                event_url = str(item.get("url") or page_url)
                description = str(item.get("description") or "Event details published by Number 52 Sauna.")
                record = _record(
                    title, start, event_url, "sauna",
                    f"{description} Official Number 52 Sauna listing.",
                    source="Number 52 Sauna official website", location=location,
                )
                record["end"] = max(end, start + timedelta(minutes=1))
                record["date_confidence"] = "structured"
                events.append(record)

    # Expand recurring offers only when the official page still publishes the
    # matching offer and weekday, so removed/changed offers aren't invented.
    offers_url = f"{base_url}/our-offers/"
    offers_body = next((body for url, body in pages if url == offers_url), "")
    if offers_body:
        visible_text = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", " ", offers_body, flags=re.I | re.S)
        visible_text = html.unescape(re.sub(r"<[^>]+>", " ", visible_text))
        visible_text = re.sub(r"\s+", " ", visible_text).strip()
        recurring = (
            # Offers published on the official offers page.
            (re.compile(r"30.?s\s*&\s*Under Night.{0,120}?Every Monday.{0,40}?7\s*[–-]\s*10\s*pm", re.I),
             "30’s & Under Night at Number 52 Sauna", "weekday", 0, 19, 22),
            (re.compile(r"Dads\s*&\s*Lads Night.{0,120}?Every Tuesday.{0,40}?7\s*[–-]\s*10\s*pm", re.I),
             "Dads & Lads Night at Number 52 Sauna", "weekday", 1, 19, 22),
            (re.compile(r"Couples\s*&\s*Bring a Friend Day.{0,120}?Every Wednesday", re.I),
             "Couples & Bring a Friend Day at Number 52 Sauna", "weekday", 2, 11, 22),
            (re.compile(r"Under 30.?s.{0,100}?£12 entry every Monday, Tuesday\s*&\s*Wednesday", re.I),
             "Under 30’s £12 Entry at Number 52 Sauna", "weekday", (0, 1, 2), 11, 22),
        )
        now = dt_util.now().replace(tzinfo=None)
        last_day = (today + timedelta(days=180)).date()
        day = today.date()
        while day <= last_day:
            if day.weekday() in (0, 1, 2):
                for pattern, title, kind, weekdays, start_hour, end_hour in recurring:
                    if kind != "weekday" or not pattern.search(visible_text):
                        continue
                    if day.weekday() not in (weekdays if isinstance(weekdays, tuple) else (weekdays,)):
                        continue
                    start = datetime.combine(day, datetime.min.time()).replace(hour=start_hour)
                    end = datetime.combine(day, datetime.min.time()).replace(hour=end_hour)
                    if start >= now:
                        record = _record(
                            title, start, offers_url, "sauna",
                            "Recurring offer published by Number 52 Sauna. Check the official page for current terms and any changes.",
                            source="Number 52 Sauna official website",
                            location="Number 52 Sauna, Newcastle upon Tyne, United Kingdom",
                        )
                        record["end"] = end
                        record["date_confidence"] = "structured"
                        events.append(record)
            day += timedelta(days=1)

    # The venue's published recurring schedule identifies Fetish Night on
    # the 1st/3rd Thursday and Sports/Chav Night on the 2nd/4th Thursday.
    # Rotating Friday/Saturday themes are taken from their individual event
    # pages above rather than assigning invented weekdays to them.
    for offset in range(0, 181):
        day = (today + timedelta(days=offset)).date()
        if day.weekday() != 3:
            continue
        occurrence = (day.day - 1) // 7 + 1
        if occurrence not in (1, 2, 3, 4):
            continue
        if occurrence in (1, 3):
            title = "Fetish Night at Number 52 Sauna"
        else:
            title = "Sports/Chav Night at Number 52 Sauna"
        start = datetime.combine(day, datetime.min.time()).replace(hour=18)
        end = start + timedelta(hours=4)
        if start < dt_util.now().replace(tzinfo=None):
            continue
        record = _record(
            title, start, f"{base_url}/our-events/", "sauna",
            "Recurring themed night listed in public Number 52 Sauna event information. "
            "Confirm the date with the venue before travelling.",
            source="Number 52 Sauna published recurring schedule",
            location="Number 52 Sauna, Newcastle upon Tyne, United Kingdom",
        )
        record["end"] = end
        record["date_confidence"] = "structured"
        events.append(record)

    _LOGGER.info("Number 52 Sauna source returned %s dated or recurring events", len(events))
    return events


async def async_discover_events(hass, country: str = "", location: str = "", ticketmaster_api_key: str = "", region: str = "", county: str = "", city: str = "", area: str = "") -> list[dict]:
    """Search public event sources at several levels of the configured location."""
    session = async_get_clientsession(hass)
    today = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    country = (country or "").strip()
    location = (location or "").strip()
    # Resolve independent location metadata concurrently so network latency
    # does not add together before the event searches even begin.
    code, coordinates = await asyncio.gather(
        _country_code(session, country),
        _geocode_location(session, location or city or county or region, country),
    )
    if coordinates:
        _LOGGER.info("Using 30 km event-search radius around configured location %s", location or city or county or region)
    else:
        _LOGGER.warning("Could not geocode configured location; 30 km radius cannot be enforced for structured event results")

    # Keep the existing broad searches, then run focused searches against each
    # configured locality. A city-only query misses county-wide and regional
    # festivals; a country-only query buries smaller local listings.
    searches = [(cat, query, location) for cat, query in SEARCHES]
    locality_levels = []
    for value in (area, city, county, region, location):
        value = (value or "").strip()
        if value and value.casefold() not in {item.casefold() for item in locality_levels}:
            locality_levels.append(value)

    local_queries = (
        ("community", 'events calendar festival fair meetup'),
        ("community", 'what\'s on events this weekend OR next month'),
        ("community", 'concert theatre comedy exhibition events'),
        ("community", 'workshop convention expo conference dates'),
        ("pride", 'LGBTQ Pride events festival parade'),
        ("gay", 'gay events social meetup dates'),
        ("gay", '"gay events" calendar near me dates'),
        ("gay", '"gay men" social event meetup dates'),
        ("gay", 'gay pride festival parade 2026 OR 2027 dates'),
        ("lesbian", 'lesbian events meetup festival dates'),
        ("bisexual", 'bisexual community events dates'),
        ("transgender", 'trans community events dates'),
        ("queer", 'queer LGBTQ community events dates'),
        ("sauna", '"gay sauna" events calendar'),
        ("sauna", '"sauna" themed nights event dates'),
        ("kink", 'kink BDSM fetish event calendar dates'),
        ("chastity", 'chastity event meetup Locktober dates'),
        ("adult", 'adults only 18+ public event dates'),
        # Source-focused searches complement broad discovery without scraping
        # sites that do not expose a stable public API. Results still pass through
        # the same date extraction and cross-source deduplication pipeline.
        ("lgbtq", 'site:queerldn.uk events'),
        ("lgbtq", 'site:wherequeersgo.com/london/events LGBTQ'),
        ("lgbtq", 'site:outsavvy.com LGBTQ events'),
        ("community", 'site:eventbrite.com events'),
        ("community", 'site:meetup.com events'),
        ("community", 'site:facebook.com/events public event'),
        # These indexed searches broaden LGBTQ+ coverage beyond London-only sources.
        # They complement public RSS search; they are not direct provider integrations.
        ("lgbtq", 'site:outsavvy.com/events LGBTQ OR queer'),
        ("lgbtq", 'site:eventbrite.co.uk LGBTQ OR queer events'),
        ("lgbtq", 'site:meetup.com LGBTQ OR queer events'),
        ("lgbtq", 'site:gaydio.co.uk events LGBTQ'),
        ("lgbtq", 'site:attitude.co.uk events Pride LGBTQ'),
    )
    # Searching every query at every configured locality multiplies into
    # hundreds of RSS requests and routinely exceeds the integration's overall
    # timeout. Search the two most specific distinct locality levels instead;
    # broad country-wide searches above still provide wider coverage.
    focused_localities = locality_levels[:2] or [location]
    for locality in focused_localities:
        for category, query in local_queries:
            searches.append((category, query, locality))

    # Year-specific queries add useful coverage but run only at the most
    # specific locality to keep the total request count bounded.
    for year in (today.year, today.year + 1):
        locality = focused_localities[0]
        searches.extend([
            ("community", f'festival fair events {year} dates', locality),
            ("community", f'concert theatre exhibition events {year}', locality),
            ("pride", f'Pride festival parade {year} dates', locality),
            ("kink", f'kink fetish convention events {year}', locality),
        ])

    # Bound concurrency and each RSS request so a single slow provider cannot
    # hold up the entire search.
    semaphore = asyncio.Semaphore(20)
    async def fetch_one(category, query, search_location):
        async with semaphore:
            return await _fetch_rss(
                session, category, query, country, location, code, today,
                search_location=search_location,
            )
    # Run the structured API search alongside RSS instead of making users
    # wait for two sequential discovery phases.
    rss_task = asyncio.gather(*(fetch_one(cat, query, locality) for cat, query, locality in searches))
    ticketmaster_task = _fetch_ticketmaster(
        session, (ticketmaster_api_key or "").strip(), code, today,
        coordinates=coordinates, radius_km=30,
    )
    sauna52_task = _fetch_sauna52_events(session, today)
    # Only include Number 52 events when it is actually the closest mapped
    # sauna to the configured location. This reuses the same 30 km venue
    # discovery logic exposed by the Nearest Sauna sensor.
    nearest_saunas_task = async_discover_nearest_saunas(
        hass, country=country, location=location or city or county or region
    )
    rss, ticketmaster, sauna52, nearest_saunas = await asyncio.gather(
        rss_task, ticketmaster_task, sauna52_task, nearest_saunas_task
    )
    events = [item for batch in rss for item in batch]
    events.extend(ticketmaster)
    nearest_name = str(nearest_saunas[0].get("name", "") if nearest_saunas else "").casefold()
    number52_is_nearest = (
        "number 52" in nearest_name
        or "number52" in nearest_name.replace(" ", "")
        or "number52sauna.co.uk" in str(nearest_saunas[0].get("website", "") if nearest_saunas else "").casefold()
    )
    if number52_is_nearest:
        events.extend(sauna52)
    else:
        _LOGGER.info(
            "Skipping Number 52 events because it is not the closest mapped sauna to configured location %s",
            location or city or county or region or "unspecified",
        )

    # RSS can independently return Number 52 listings, so apply the same
    # nearest-venue rule to those results instead of only gating its official feed.
    if not number52_is_nearest:
        number52_pattern = re.compile(
            r"number\s*52|number52sauna\.co\.uk|scotswood road",
            re.IGNORECASE,
        )
        events = [
            item for item in events
            if not number52_pattern.search(" ".join(str(item.get(key, "")) for key in (
                "summary", "description", "location", "url", "source"
            )))
        ]

    _LOGGER.info(
        "Event discovery completed for %s, %s: %s search queries returned %s dated events before deduplication",
        location or "unspecified location", country or "unspecified country", len(searches), len(events),
    )
    return _deduplicate(events)


async def async_discover_nearest_saunas(hass, country: str = "", location: str = "") -> list[dict]:
    """Find nearby sauna venues from OpenStreetMap plus a known-venue fallback."""
    session = async_get_clientsession(hass)
    coordinates = await _geocode_location(session, location, country)
    if not coordinates:
        return []
    lat, lon = coordinates
    query = f"""[out:json][timeout:20];
(
  nwr(around:30000,{lat},{lon})["leisure"="sauna"];
  nwr(around:30000,{lat},{lon})["amenity"="sauna"];
  nwr(around:30000,{lat},{lon})["building"="sauna"];
);
out center tags;"""
    # Keep the address-based fallback working even when the Overpass service is
    # unavailable or rate-limited.
    payload = {"elements": []}
    try:
        async with asyncio.timeout(25):
            async with session.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.8.4"},
            ) as response:
                if response.status == 200:
                    payload = await response.json()
                else:
                    _LOGGER.debug("OpenStreetMap Overpass returned HTTP %s; using venue fallbacks", response.status)
    except Exception as err:
        _LOGGER.debug("Could not query OpenStreetMap Overpass; using venue fallbacks: %s", err)

    def distance_km(lat1, lon1, lat2, lon2):
        from math import asin, cos, radians, sin, sqrt
        dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
        value = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return 6371 * 2 * asin(sqrt(min(1, value)))

    found = []
    for item in payload.get("elements", []):
        tags = item.get("tags", {})
        center = item.get("center", {})
        sauna_lat = item.get("lat", center.get("lat"))
        sauna_lon = item.get("lon", center.get("lon"))
        if sauna_lat is None or sauna_lon is None:
            continue
        address = ", ".join(str(tags[key]) for key in (
            "addr:housenumber", "addr:street", "addr:city", "addr:postcode"
        ) if tags.get(key))
        found.append({
            "name": tags.get("name") or tags.get("brand") or "Unnamed sauna",
            "distance_km": round(distance_km(lat, lon, float(sauna_lat), float(sauna_lon)), 1),
            "address": address,
            "website": tags.get("website") or tags.get("contact:website") or "",
            "phone": tags.get("phone") or tags.get("contact:phone") or "",
            "latitude": float(sauna_lat),
            "longitude": float(sauna_lon),
            "osm_url": f"https://www.openstreetmap.org/{item.get('type', 'node')}/{item.get('id')}",
        })
    # Number 52 is a known sauna in Newcastle. Use its published address as
    # an independent venue fallback when it is not tagged as a sauna in OSM.
    # This lookup runs even if the Overpass API is unavailable.
    try:
        async with asyncio.timeout(10):
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": "Number 52 Sauna, 52 Scotswood Road, Newcastle upon Tyne, NE4 7JB, United Kingdom",
                    "format": "jsonv2",
                    "limit": "1",
                },
                headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.8.4 (sauna discovery)"},
            ) as response:
                if response.status == 200:
                    venue_matches = await response.json()
                    if venue_matches:
                        venue_lat = float(venue_matches[0]["lat"])
                        venue_lon = float(venue_matches[0]["lon"])
                        venue_distance = distance_km(lat, lon, venue_lat, venue_lon)
                        is_duplicate = any(
                            "number 52" in venue["name"].casefold()
                            or "scotswood road" in venue.get("address", "").casefold()
                            for venue in found
                        )
                        if venue_distance <= 30 and not is_duplicate:
                            found.append({
                                "name": "Number 52 Sauna",
                                "distance_km": round(venue_distance, 1),
                                "address": "52 Scotswood Road, Newcastle upon Tyne, NE4 7JB",
                                "website": "https://www.number52sauna.co.uk/",
                                "phone": "0191 2212189",
                                "latitude": venue_lat,
                                "longitude": venue_lon,
                                "osm_url": "https://www.openstreetmap.org/search?query=Number%2052%20Sauna%2C%20Newcastle",
                            })
    except Exception as err:
        _LOGGER.debug("Could not resolve Number 52 fallback listing: %s", err)

    # Last-resort UK directory fallback. This is a small maintained index based on
    # the public Gay Sauna Guide UK directory; it is not scraped at runtime.
    # Only geocode entries matching the configured town/city to avoid bulk
    # geocoding and to keep the nearest-distance estimate tied to a venue result.
    if not found and (country or "").strip().casefold() in {"uk", "united kingdom", "great britain"}:
        directory_url = "https://www.gaysaunaguide.net/gay-saunas-in-the-uk/"
        uk_venues = (
            ("Basement", "Manchester"),
            ("Dolphin Sauna", "Wallasey"),
            ("Heat Sauna", "Stockport"),
            ("Nero's Sauna", "Bury"),
            ("Sauna Sauna", "Northwich"),
            ("Gentry Hull", "Hull"),
            ("Plastic Ivy Sauna", "Dewsbury"),
            ("Steam Complex", "Leeds"),
            ("The Boiler Room", "Sheffield"),
            ("Club Zeus", "Mansfield"),
            ("Greenhouse Sauna Darlaston", "Darlaston"),
            ("Heroes Health Club", "Stourbridge"),
            ("Just For You", "Birmingham"),
            ("ME1 Sauna & Steam", "Rochester"),
            ("The Brighton Sauna", "Brighton"),
            ("The Boiler Room Sauna", "Brighton"),
            ("Tropics Day Spa", "Portsmouth"),
            ("Manticore Spa", "Plymouth"),
            ("Saunabar", "Bournemouth"),
            ("Steamer Quay", "Torquay"),
            ("Touch Sauna", "Swindon"),
            ("Greenhouse Sauna Luton", "Luton"),
            ("Steamworks Sauna", "Edinburgh"),
            ("The Pipeworks", "Glasgow"),
            ("Greenhouse Sauna Newport", "Newport"),
        )
        normalise_place = lambda value: re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()
        configured_place = normalise_place(location)
        # Accept common shortened forms such as "Newcastle" for "Newcastle upon Tyne".
        candidates = [
            (name, city) for name, city in uk_venues
            if configured_place and (
                configured_place == normalise_place(city)
                or configured_place in normalise_place(city).split()
                or normalise_place(city) in configured_place
            )
        ]
        for name, city in candidates[:2]:
            try:
                async with asyncio.timeout(10):
                    async with session.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={"q": f"{name}, {city}, United Kingdom", "format": "jsonv2", "limit": "1"},
                        headers={"User-Agent": "HomeAssistant-ChastityCalendar/1.8.5 (sauna discovery)"},
                    ) as response:
                        if response.status != 200:
                            continue
                        matches = await response.json()
                if not matches:
                    continue
                venue_lat, venue_lon = float(matches[0]["lat"]), float(matches[0]["lon"])
                venue_distance = distance_km(lat, lon, venue_lat, venue_lon)
                if venue_distance <= 30:
                    found.append({
                        "name": name,
                        "distance_km": round(venue_distance, 1),
                        "address": city + ", United Kingdom",
                        "website": "",
                        "phone": "",
                        "latitude": venue_lat,
                        "longitude": venue_lon,
                        "osm_url": directory_url,
                        "source": "Gay Sauna Guide UK directory",
                        "source_url": directory_url,
                    })
            except Exception as err:
                _LOGGER.debug("Could not resolve UK directory sauna %r: %s", name, err)

    return sorted(found, key=lambda sauna: sauna["distance_km"])