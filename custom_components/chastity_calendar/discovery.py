"""Best-effort multi-source discovery of public, dated community events."""
from __future__ import annotations
import asyncio
import calendar as _calendar
from difflib import SequenceMatcher
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote, quote_plus, urljoin, urlsplit, urlunsplit
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
    ("kink", '"furry meetup" OR "furry convention" OR furmeet events dates'),
    ("kink", '"furry social" OR "furry gathering" OR "furry festival" dates'),

    # Platform-specific searches supplement the public convention directories below.
    # These platforms do not all expose stable, anonymous event-calendar pages,
    # so discover listings through indexed public pages rather than scraping private feeds.
    ("kink", 'site:meetup.com furry (furmeet OR "furry meetup" OR convention)'),
    ("kink", 'site:eventbrite.co.uk furry (furmeet OR convention OR meetup)'),
    ("kink", 'site:facebook.com/events furry (furmeet OR convention OR meetup)'),
    ("kink", 'site:reddit.com/r/furry (furmeet OR convention OR meetup) dates'),
    ("kink", 'site:howlr.app (event OR meetup OR furmeet) furry'),
    ("kink", 'site:en.wikifur.com/wiki furry convention UK dates'),
    ("kink", 'site:discord.com/invite furry UK furmeet event'),
    ("kink", 'site:disboard.org furry UK meetup community'),
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
    ("kink", 'site:regulation.co.uk/pages/uk-fetish-calendar UK fetish calendar events dates'),
    ("kink", 'site:regulation.co.uk fetish events UK calendar'),
    ("kink", 'site:fetish.events/gb upcoming UK kink fetish events'),
    ("kink", 'site:kinkready.com/events UK kink fetish dates'),
    ("kink", 'site:thefetishnetwork.com/events UK fetish kink events dates'),
    # Source-focused searches help surface actual dated listings, not only broad articles.
    ("kink", 'site:othernights.com/e/ kink BDSM fetish events dates'),
    ("kink", 'site:kinkready.com/events upcoming BDSM kink fetish events'),
    ("kink", 'site:londonalternativemarket.com event dates kink market'),
    ("kink", 'site:outsavvy.com kink fetish BDSM queer events dates'),
    ("kink", 'site:skiddle.com London fetish BDSM events dates'),
    ("kink", 'site:dice.fm London fetish queer kink events dates'),
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
    """Extract an event date from the past 180 days through the next two years.

    Retaining a short history lets calendar views show recently completed events
    on their original dates. Search snippets often omit the year, so yearless
    dates are resolved to the nearest eligible occurrence. Numeric dates use
    UK-style day/month/year; ISO dates remain unambiguous.
    """
    # Some convention directories render dates compactly in labels, e.g. SEP262026.
    # Insert separators so the normal date parser can handle those listings too.
    text = re.sub(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?([0-9]{1,2})(20[0-9]{2})\b",
        r"\1 \2 \3", text, flags=re.IGNORECASE,
    )
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

    lower = (today - timedelta(days=180)).date()
    upper = (today + timedelta(days=730)).date()
    eligible = [value for value in found_dates if lower <= value.date() <= upper]
    return min(eligible, key=lambda value: value.date()) if eligible else None

def _find_event_datetime(text: str, today: datetime):
    """Extract a date and an explicit local clock time from a listing snippet."""
    event_date = _find_future_date(text, today)
    if event_date is None:
        return None
    # Accept common listing formats such as 6pm, 6:00 pm, 18:00, and 6:00pm.
    time_match = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)(?=\b|\s|[,.;]|$)"
        r"|\b([01]?\d|2[0-3]):([0-5]\d)\b",
        text,
        re.IGNORECASE,
    )
    if not time_match:
        return event_date
    if time_match.group(4) is not None:
        hour, minute = int(time_match.group(4)), int(time_match.group(5))
    else:
        hour, minute = int(time_match.group(1)), int(time_match.group(2) or 0)
        meridiem = re.sub(r"[^ap]", "", time_match.group(3).casefold())
        if hour < 1 or hour > 12:
            return event_date
        hour = hour % 12 + (12 if meridiem == "p" else 0)
    return event_date.replace(hour=hour, minute=minute)


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
    return {
        "summary": title[:180] or "Possible event",
        # A midnight timestamp from a date-only listing represents an all-day
        # event, not a timed event starting at 00:00. Keep this explicit so the
        # calendar entity can emit date values rather than timezone-aware datetimes.
        "all_day": start.time() == datetime.min.time(),
        "start": start, "end": start + (timedelta(hours=2) if start.time() != datetime.min.time() else timedelta(days=1)),
        "description": description[:1200], "url": url, "category": category,
        "categories": _category_tags(category, title, description),
        "location": location, "source": source, "sources": [source],
        "source_links": [url] if url else [], "last_seen": dt_util.now().isoformat(),
        "date_confidence": date_confidence,
    }


async def _fetch_structured_event_date(session, url: str, today: datetime, include_end: bool = False):
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
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                parsed = dt_util.as_local(parsed).replace(tzinfo=None)
        except (ValueError, TypeError):
            parsed = _find_future_date(str(raw), today)
        if parsed and (today - timedelta(days=180)).date() <= parsed.date() <= (today + timedelta(days=730)).date():
            candidates.append(parsed)

    # FurryGuides publishes the schedule in its "Quick Facts" list, where
    # "Time" is followed by a range such as "12 PM - 6 PM". Combine the
    # explicit start time with the event date from metadata or visible text.
    visible_text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    normalized_text = re.sub(r"\s+", " ", visible_text)
    # FurryGuides sometimes publishes only a start time (for example,
    # "Time 2 PM") instead of a start/end range. Accept either form so timed
    # events are not incorrectly emitted as all-day events.
    clock_pattern = r"(?:\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|(?:[01]?\d|2[0-3]):[0-5]\d)"
    time_match = re.search(
        rf"\bTime\s+({clock_pattern})(?:\s*(?:-|–|—|to|till|until)\s*({clock_pattern}))?",
        normalized_text,
        re.I,
    )
    if time_match:
        date_candidate = min(candidates, key=lambda item: item.date()) if candidates else _find_future_date(normalized_text, today)
        if date_candidate:
            def parse_clock(raw_time):
                if not raw_time:
                    return None
                time_text = re.sub(r"\s+", " ", raw_time).replace(".", "").upper()
                for time_format in ("%H:%M", "%I:%M %p", "%I %p"):
                    try:
                        return datetime.strptime(time_text, time_format).time()
                    except ValueError:
                        continue
                return None

            parsed_time = parse_clock(time_match.group(1))
            if parsed_time:
                timed_start = datetime.combine(date_candidate.date(), parsed_time)
                if (today - timedelta(days=180)).date() <= timed_start.date() <= (today + timedelta(days=730)).date():
                    if include_end:
                        parsed_end_time = parse_clock(time_match.group(2))
                        # A lone published start time runs until midnight.
                        timed_end = (
                            datetime.combine(date_candidate.date(), parsed_end_time)
                            if parsed_end_time else datetime.combine(date_candidate.date() + timedelta(days=1), datetime.min.time())
                        )
                        if timed_end <= timed_start:
                            timed_end += timedelta(days=1)
                        return timed_start, timed_end
                    return timed_start
    fallback = min(candidates, key=lambda item: item.date()) if candidates else None
    return (fallback, None) if include_end else fallback

def _extract_furryguides_page_name(body: str, url: str) -> str:
    """Read the group name from the heading on a FurryGuides event page."""
    parsed_url = urlsplit(url)
    if parsed_url.netloc.casefold().removeprefix("www.") != "furryguides.com":
        return ""
    if not re.match(r"^/events/[^/]+/?$", parsed_url.path, re.IGNORECASE):
        return ""

    # The main heading is the canonical group name shown to visitors.
    match = re.search(r"<h1\b[^>]*>(.*?)</h1\s*>", body, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    name = html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
    return re.sub(r"\s+", " ", name).strip()[:180]


async def _fetch_structured_event_name(session, url: str) -> str:
    """Extract a canonical event name from schema.org Event metadata."""
    if urlsplit(url).scheme not in {"http", "https"}:
        return ""
    try:
        async with asyncio.timeout(6):
            async with session.get(
                url,
                headers={"User-Agent": "HomeAssistant-CommunityEventsCalendar/2.0.3"},
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    return ""
                body = (await response.text())[:1500000]
    except Exception as err:
        _LOGGER.debug("Could not inspect event title page %s: %s", url, err)
        return ""
    # FurryGuides group pages use their top-level heading as the displayed name.
    # Prefer it over schema.org metadata, which may be missing or refer to a listing.
    page_name = _extract_furryguides_page_name(body, url)
    if page_name:
        return page_name

    pattern = re.compile(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script\s*>', re.I | re.S)
    names = []
    for raw in pattern.findall(body):
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
                    name = value.get("name")
                    if isinstance(name, str) and name.strip():
                        names.append(html.unescape(name).strip())
                stack.extend(item for key, item in value.items() if key not in {"@context"})
    return names[0] if names else ""

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
    structured_title_checks = 0
    lgbtq_categories = {"pride", "gay", "lesbian", "bisexual", "transgender", "queer", "lgbtq"}
    structured_date_categories = lgbtq_categories | {"kink", "chastity", "adult"}
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        description = item.findtext("description") or ""
        link = item.findtext("link") or ""
        if not title.strip() or not link.strip(): continue
        event_text = f"{title} {description}"
        event_date = _find_event_datetime(event_text, today)
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
        # Prefer the original event's structured name over a news headline.
        canonical_title = ""
        max_title_checks = 8 if category in lgbtq_categories else 4
        if category in structured_date_categories and structured_title_checks < max_title_checks:
            structured_title_checks += 1
            canonical_title = await _fetch_structured_event_name(session, link)
        if canonical_title:
            title = canonical_title
        else:
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
            if not (today - timedelta(days=180)).date() <= start.date() <= (today + timedelta(days=730)).date(): continue
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
    """Merge same-day duplicate listings while preserving distinct events."""
    merged = {}
    title_date_to_key = {}

    def normalise(value):
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

    def locations_compatible(left, right):
        """Do not merge same-title events at clearly different venues."""
        left_location = normalise(left.get("location"))
        right_location = normalise(right.get("location"))
        if not left_location or not right_location:
            return True
        return SequenceMatcher(None, left_location, right_location).ratio() >= 0.65

    for event in events:
        title_key = normalise(event.get("summary"))
        date_key = event["start"].date().isoformat()
        location_key = normalise(event.get("location"))
        identity = (title_key, date_key, location_key)
        key = title_date_to_key.get(identity)
        if key is None:
            # Sources often add subtitles or small wording variations. Match
            # similar names on the same start date, but never combine listings
            # that clearly point to different venues.
            for (existing_title, existing_date, _existing_location), existing_key in title_date_to_key.items():
                existing = merged[existing_key]
                if (
                    existing_date == date_key
                    and SequenceMatcher(None, title_key, existing_title).ratio() >= 0.88
                    and locations_compatible(existing, event)
                ):
                    key = existing_key
                    break
        if key is None:
            key = ("event", len(merged))
            merged[key] = event
        else:
            old = merged[key]
            old_end = old["end"]
            new_start, new_end = event["start"], event["end"]
            if event.get("date_confidence") == "structured" or old.get("date_confidence") != "structured":
                old["start"] = new_start
                # Keep the widest known span for a multi-day occurrence rather
                # than shrinking it to a shorter duplicate listing.
                if type(old_end) is type(new_end):
                    old["end"] = max(old_end, new_end)
                else:
                    old["end"] = new_end
            else:
                if type(old_end) is type(new_end):
                    old["end"] = max(old_end, new_end)
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



def _is_target_event(event: dict) -> bool:
    """Keep LGBTQ+ identity/community and kink or fetish events.

    RSS search labels alone are not sufficient: broad searches can return
    unrelated listings. Match the listing's own title, description, tags,
    category, venue, source, or URL instead.
    """
    fields = (
        "summary", "title", "description", "location", "url", "source",
        "category", "categories", "tags", "event_type",
    )
    values = []
    for key in fields:
        value = event.get(key, "")
        if isinstance(value, (list, tuple, set)):
            values.extend(str(item) for item in value if item)
        elif value:
            values.append(str(value))
    values.extend(str(item) for item in (event.get("sources") or []) if item)
    text = " ".join(values).casefold()

    # Identity labels and communities: include the full LGBTQIA+ spectrum and
    # commonly used names for events, not just the acronym itself.
    patterns = (
        r"\blgbt(?:q|qia)?\+?(?=\W|$)", r"\bqueer\b", r"\bpride\b",
        r"\bgay\b", r"\blesbian\b", r"\bbisexual\b", r"\bbi pride\b",
        r"\bpansexual\b", r"\bpansexuality\b", r"\bomnisexual\b",
        r"\btrans(?:gender)?\b", r"\btransmasc(?:uline)?\b",
        r"\btransfem(?:inine)?\b", r"\bnon[- ]?binary\b",
        r"\benby\b", r"\bgenderqueer\b", r"\bgenderfluid\b",
        r"\bagender\b", r"\bintersex\b", r"\basexual\b", r"\baromantic\b",
        r"\bdemisexual\b", r"\bdemiromantic\b", r"\bgraysexual\b",
        r"\bgreysexual\b", r"\bace community\b", r"\baro community\b",
        r"\btwo[- ]?spirit\b", r"\bsapphic\b", r"\bwlw\b", r"\bmlm\b",
        r"\bqueer women\b", r"\bqueer men\b", r"\bchosen family\b",
        r"\bdrag\b", r"\bvoguing\b", r"\bballroom scene\b",
        r"\bqueer film\b", r"\blgbt film\b", r"\bqueer art\b",
        r"\bgender affirming\b", r"\bhiv awareness\b", r"\bhiv support\b",
        # Kink, fetish and adjacent event communities.
        r"\bkink\b", r"\bfetish\b",
        r"\bbdsm\b", r"\bbondage\b", r"\bdominance\b", r"\bsubmission\b",
        r"\bsadomasochism\b", r"\bleather\b", r"\blatex\b", r"\brubber\b",
        r"\bshibari\b", r"\brope play\b", r"\bpup play\b", r"\bpuppy play\b",
        r"\bpet play\b", r"\bchastity\b", r"\blocktober\b",
        r"\bpower exchange\b", r"\bdungeon\b", r"\bfindom\b",
        r"\bfinancial domination\b", r"\bgear social\b", r"\bfoot fetish\b",
        r"\bimpact play\b", r"\bsensory play\b", r"\broleplay kink\b",
        r"\bcrossdressing\b", r"\bfurry\b", r"\bfurmeet\b", r"\bfursuit\b",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


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


async def _fetch_furry_directory_events(session, today: datetime) -> list[dict]:
    """Read public furry event listings from UK directories and England listings."""
    sources = (
        ("FurryCons.com", "https://furrycons.com/calendar/calendar.php?loc=uk"),
        ("FurryGuides Events", "https://furryguides.com/events"),
        ("FurryGuides UK", "https://furryguides.com/conventions/countries/united-kingdom"),
        ("FurDar England", "https://furdar.org/area/1-england/"),
    )
    lower = (today - timedelta(days=180)).date()
    upper = (today + timedelta(days=730)).date()

    async def fetch_source(source, url):
        try:
            async with asyncio.timeout(12):
                async with session.get(
                    url,
                    headers={"User-Agent": "HomeAssistant-CommunityEventsCalendar/2.3 (public event calendar discovery)"},
                    allow_redirects=True,
                ) as response:
                    if response.status != 200:
                        _LOGGER.debug("%s returned HTTP %s", source, response.status)
                        return []
                    body = (await response.text())[:2000000]
        except Exception as err:
            _LOGGER.debug("Could not fetch %s: %s", source, err)
            return []
        candidates = []
        # Prefer explicit Schema.org event metadata when the site provides it.
        for item in _iter_jsonld_events(body):
            title = str(item.get("name") or "").strip()
            raw_start = item.get("startDate")
            if not title or not isinstance(raw_start, str):
                continue
            try:
                start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                start = _find_future_date(raw_start, today)
            context = title + " " + str(item.get("description", ""))
            if start and lower <= start.date() <= upper and re.search(
                r"\bfurr|\bfurmeet\b|\bfursuit\b|\banthro\b|\bscotiacon\b|\bconfuzzled\b|\baberacon\b|\bpawsome\b|\bwild north\b|\bfurcation\b",
                context, re.I,
            ):
                candidates.append((title, start, str(item.get("url") or url), str(item.get("description") or ""), str(item.get("location") or ""), "structured"))
        # FurryCons uses dated table rows; FurDar may use event cards. Parse
        # bounded row/card fragments and require an explicit furry-context match.
        fragments = re.findall(
            r"<tr\b[^>]*>.*?</tr\s*>|<article\b[^>]*>.*?</article\s*>|<li\b[^>]*>.*?</li\s*>",
            body, re.I | re.S,
        )
        for fragment in fragments:
            plain = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
            plain = re.sub(r"\s+", " ", plain).strip()
            start = _find_future_date(plain, today)
            if not start or not lower <= start.date() <= upper:
                continue
            links = re.findall(r"<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a\s*>", fragment, re.I | re.S)
            if not links:
                continue
            title, event_url = "", url
            for href, label in links:
                label = html.unescape(re.sub(r"<[^>]+>", " ", label))
                label = re.sub(r"\s+", " ", label).strip()
                if label and len(label) > 2:
                    title = label
                    event_url = urljoin(url, href)
                    break
            if title:
                # The FurryGuides listing supplies the event date, while the
                # detail page's "Time" field / Event startDate supplies its
                # actual start time. Prefer that explicit datetime when present.
                detail_result = await _fetch_structured_event_date(session, event_url, today, include_end=True)
                detail_start, detail_end = detail_result if isinstance(detail_result, tuple) else (detail_result, None)
                if detail_start is not None:
                    start = detail_start
                candidates.append((title, start, event_url, plain, "", "extracted_from_source_listing", detail_end))
        results = []
        seen = set()
        for candidate in candidates:
            title, start, event_url, description, location, confidence = candidate[:6]
            detail_end = candidate[6] if len(candidate) > 6 else None
            # Listing metadata can contain a long SEO title instead of the
            # concise group/event name. For FurryGuides event pages, use the
            # canonical heading from the detail page (e.g. "Birmingham Furs").
            if re.search(r"^https?://(?:www\.)?furryguides\.com/events/[^/?#]+", event_url, re.I):
                canonical_title = await _fetch_structured_event_name(session, event_url)
                if canonical_title:
                    title = canonical_title
            key = (re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip(), start.date())
            if key in seen:
                continue
            seen.add(key)
            record = _record(
                title, start, event_url, "kink",
                f"Furry community event listing from {source}. {description[:800]} Verify dates, venue and access details with the organiser.",
                source=source, location=location, date_confidence=confidence,
            )
            if detail_end is not None:
                record["end"] = detail_end
            elif start.time() != datetime.min.time() and "furryguides.com" in event_url.casefold():
                # If the source gives a start time but no end time, keep the event
                # visible from its start until midnight rather than assuming 2 hours.
                record["end"] = datetime.combine(start.date() + timedelta(days=1), datetime.min.time())
            record["categories"] = sorted(set(record.get("categories", [])) | {"furry", "community"})
            results.append(record)
        _LOGGER.info("%s yielded %s dated furry events", source, len(results))
        return results

    batches = await asyncio.gather(*(fetch_source(source, url) for source, url in sources))
    return [item for batch in batches for item in batch]

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
    furry_task = _fetch_furry_directory_events(session, today)
    rss, ticketmaster, furry = await asyncio.gather(
        rss_task, ticketmaster_task, furry_task
    )
    events = [item for batch in rss for item in batch]
    events.extend(ticketmaster)
    events.extend(furry)

    _LOGGER.info(
        "Event discovery completed for %s, %s: %s search queries returned %s dated events before deduplication",
        location or "unspecified location", country or "unspecified country", len(searches), len(events),
    )
    # Broad RSS searches sometimes return unrelated events (for example,
    # ordinary comedy listings). Only retain listings whose own metadata/text
    # identifies one of the integration's supported event topics.
    relevant_events = [item for item in events if _is_target_event(item)]
    _LOGGER.info(
        "Filtered discovery results to %s LGBTQ+/kink/fetish events",
        len(relevant_events),
    )
    return _deduplicate(relevant_events)


