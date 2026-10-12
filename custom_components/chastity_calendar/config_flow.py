"""Config and options flow for Chastity Challenge Calendar."""

import logging
from urllib.parse import quote

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SKIP = "— Skip this level —"
COUNTRY_FALLBACK = [
    "Australia", "Austria", "Belgium", "Brazil", "Canada", "Denmark",
    "Finland", "France", "Germany", "India", "Ireland", "Italy", "Japan",
    "Mexico", "Netherlands", "New Zealand", "Norway", "Portugal", "Singapore",
    "South Africa", "South Korea", "Spain", "Sweden", "Switzerland",
    "United Kingdom", "United States",
]

# CountriesNow lists administrative subdivisions, which do not always include
# familiar geographic regions such as the English regions. Add these aliases
# to the relevant dropdown while preserving API-provided options.
COUNTRY_REGIONS = {
    "United Kingdom": [
        "East Midlands", "East of England", "London", "North East",
        "North West", "South East", "South West", "West Midlands",
        "Yorkshire and the Humber", "Scotland", "Wales", "Northern Ireland",
    ],
}

UK_REGION_COUNTIES = {
    "East Midlands": ["Derbyshire", "Leicestershire", "Lincolnshire", "Northamptonshire", "Nottinghamshire", "Rutland"],
    "East of England": ["Bedfordshire", "Cambridgeshire", "Essex", "Hertfordshire", "Norfolk", "Suffolk"],
    "London": ["Greater London"],
    "North East": ["County Durham", "Northumberland", "Tyne and Wear"],
    "North West": ["Cheshire", "Cumbria", "Greater Manchester", "Lancashire", "Merseyside"],
    "South East": ["Berkshire", "Buckinghamshire", "East Sussex", "Hampshire", "Isle of Wight", "Kent", "Oxfordshire", "Surrey", "West Sussex"],
    "South West": ["Bristol", "Cornwall", "Devon", "Dorset", "Gloucestershire", "Somerset", "Wiltshire"],
    "West Midlands": ["Herefordshire", "Shropshire", "Staffordshire", "Warwickshire", "West Midlands", "Worcestershire"],
    "Yorkshire and the Humber": ["East Riding of Yorkshire", "North Yorkshire", "South Yorkshire", "West Yorkshire"],
    "Scotland": ["Aberdeenshire", "Angus", "City of Edinburgh", "Glasgow City", "Highland", "Fife", "Perth and Kinross"],
    "Wales": ["Clwyd", "Dyfed", "Glamorgan", "Gwent", "Gwynedd", "Powys"],
    "Northern Ireland": ["County Antrim", "County Armagh", "County Down", "County Fermanagh", "County Londonderry", "County Tyrone"],
}

UK_COUNTY_CITIES = {
    "Derbyshire": ["Buxton", "Chesterfield", "Derby", "Glossop", "Ilkeston"],
    "Leicestershire": ["Hinckley", "Loughborough", "Market Harborough", "Melton Mowbray", "Leicester"],
    "Lincolnshire": ["Boston", "Grantham", "Lincoln", "Skegness", "Spalding"],
    "Northamptonshire": ["Corby", "Kettering", "Northampton", "Wellingborough"],
    "Nottinghamshire": ["Mansfield", "Newark-on-Trent", "Nottingham", "Retford", "Worksop"],
    "Bedfordshire": ["Bedford", "Dunstable", "Leighton Buzzard", "Luton"],
    "Cambridgeshire": ["Cambridge", "Ely", "Huntingdon", "Peterborough", "St Neots"],
    "Essex": ["Basildon", "Brentwood", "Chelmsford", "Colchester", "Harlow", "Southend-on-Sea"],
    "Hertfordshire": ["Hemel Hempstead", "Hertford", "St Albans", "Stevenage", "Watford"],
    "Norfolk": ["Great Yarmouth", "King's Lynn", "Norwich"],
    "Suffolk": ["Bury St Edmunds", "Felixstowe", "Ipswich", "Lowestoft"],
    "Greater London": ["Barking", "Bromley", "Camden", "Croydon", "Greenwich", "Hackney", "Hammersmith", "Islington", "Kensington", "Kingston upon Thames", "Lambeth", "Lewisham", "Newham", "Southwark", "Westminster"],
    "County Durham": ["Darlington", "Durham", "Peterlee", "Bishop Auckland"],
    "Northumberland": ["Alnwick", "Ashington", "Berwick-upon-Tweed", "Hexham"],
    "Tyne and Wear": ["Gateshead", "Newcastle upon Tyne", "South Shields", "Sunderland", "Tynemouth", "Whitley Bay"],
    "Cheshire": ["Chester", "Crewe", "Ellesmere Port", "Macclesfield", "Warrington"],
    "Cumbria": ["Barrow-in-Furness", "Carlisle", "Kendal", "Penrith", "Whitehaven"],
    "Greater Manchester": ["Bolton", "Bury", "Manchester", "Oldham", "Rochdale", "Salford", "Stockport", "Wigan"],
    "Lancashire": ["Blackburn", "Blackpool", "Burnley", "Lancaster", "Preston"],
    "Merseyside": ["Birkenhead", "Liverpool", "Southport", "St Helens", "Wallasey"],
    "Berkshire": ["Bracknell", "Maidenhead", "Newbury", "Reading", "Slough", "Windsor"],
    "Buckinghamshire": ["Aylesbury", "Buckingham", "High Wycombe", "Milton Keynes"],
    "East Sussex": ["Eastbourne", "Hastings", "Lewes", "Rye"],
    "Hampshire": ["Andover", "Basingstoke", "Fareham", "Portsmouth", "Southampton", "Winchester"],
    "Kent": ["Canterbury", "Chatham", "Dartford", "Dover", "Maidstone", "Margate", "Rochester"],
    "Oxfordshire": ["Banbury", "Bicester", "Oxford", "Witney"],
    "Surrey": ["Epsom", "Guildford", "Reigate", "Woking"],
    "West Sussex": ["Arundel", "Chichester", "Crawley", "Worthing"],
    "Bristol": ["Bristol"],
    "Cornwall": ["Falmouth", "Newquay", "Penzance", "St Austell", "Truro"],
    "Devon": ["Barnstaple", "Exeter", "Plymouth", "Torquay"],
    "Dorset": ["Bournemouth", "Dorchester", "Poole", "Weymouth"],
    "Gloucestershire": ["Cheltenham", "Cirencester", "Gloucester", "Stroud"],
    "Somerset": ["Bath", "Bridgwater", "Taunton", "Yeovil"],
    "Wiltshire": ["Chippenham", "Salisbury", "Swindon"],
    "Herefordshire": ["Hereford", "Leominster"],
    "Shropshire": ["Shrewsbury", "Telford"],
    "Staffordshire": ["Burton upon Trent", "Cannock", "Stafford", "Stoke-on-Trent"],
    "Warwickshire": ["Leamington Spa", "Nuneaton", "Rugby", "Stratford-upon-Avon", "Warwick"],
    "West Midlands": ["Birmingham", "Coventry", "Dudley", "Solihull", "Wolverhampton"],
    "Worcestershire": ["Kidderminster", "Redditch", "Worcester"],
    "East Riding of Yorkshire": ["Beverley", "Bridlington", "Goole"],
    "North Yorkshire": ["Harrogate", "Scarborough", "Skipton", "York"],
    "South Yorkshire": ["Barnsley", "Doncaster", "Rotherham", "Sheffield"],
    "West Yorkshire": ["Bradford", "Halifax", "Huddersfield", "Leeds", "Wakefield"],
}


async def _json_request(hass, url, *, method="get", payload=None, timeout=15):
    """Make a bounded request to a public location data service."""
    session = async_get_clientsession(hass)
    try:
        async with getattr(session, method)(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={"User-Agent": "ChastityCalendar/1.6 (Home Assistant integration)"},
        ) as response:
            response.raise_for_status()
            return await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.warning("Location lookup failed for %s: %s", url.split("?")[0], err)
        return None


async def _countries(hass):
    """Fetch countries online, falling back if the service is unavailable."""
    data = await _json_request(hass, "https://restcountries.com/v3.1/all?fields=name")
    if isinstance(data, list):
        names = sorted({
            item.get("name", {}).get("common", "")
            for item in data
            if isinstance(item, dict) and item.get("name", {}).get("common")
        })
        if names:
            return names
    return COUNTRY_FALLBACK


async def _regions(hass, country):
    """Fetch regions and provinces for the selected country."""
    data = await _json_request(
        hass, "https://countriesnow.space/api/v0.1/countries/states",
        method="post", payload={"country": country},
    )
    states = data.get("data", {}).get("states", []) if isinstance(data, dict) else []
    names = sorted({
        item.get("name", "").strip() for item in states
        if isinstance(item, dict) and item.get("name", "").strip()
    })
    extra = COUNTRY_REGIONS.get(country, [])
    return sorted(set(names + extra)) or [SKIP]


async def _counties(hass, country, region):
    """Load a county/sub-region dropdown; UK regions use curated county lists."""
    if country == "United Kingdom" and region in UK_REGION_COUNTIES:
        return UK_REGION_COUNTIES[region]
    # Many countries do not have a standard county layer in the source API.
    # Keep the level optional there instead of showing misleading matches.
    return [SKIP]


async def _cities(hass, country, region, county):
    """Fetch cities and towns narrowed to the selected county where supported."""
    if not region or region == SKIP:
        return [SKIP]
    if country == "United Kingdom" and county in UK_COUNTY_CITIES:
        return UK_COUNTY_CITIES[county]
    if country == "United Kingdom" and (not county or county == SKIP):
        region_counties = UK_REGION_COUNTIES.get(region, [])
        regional_cities = sorted({
            city for county_name in region_counties
            for city in UK_COUNTY_CITIES.get(county_name, [])
        })
        return regional_cities or [SKIP]
    if not county or county == SKIP:
        # For countries without a county layer, use the selected region as
        # the API's state/province value so users can still choose a city.
        data = await _json_request(
            hass, "https://countriesnow.space/api/v0.1/countries/state/cities",
            method="post", payload={"country": country, "state": region},
        )
        cities = data.get("data", []) if isinstance(data, dict) else []
        names = sorted({v.strip() for v in cities if isinstance(v, str) and v.strip()})
        return names or [SKIP]
    data = await _json_request(
        hass, "https://countriesnow.space/api/v0.1/countries/state/cities",
        method="post", payload={"country": country, "state": region},
    )
    cities = data.get("data", []) if isinstance(data, dict) else []
    names = sorted({v.strip() for v in cities if isinstance(v, str) and v.strip()})
    return names or [SKIP]


async def _areas(hass, country, region, city):
    """Fetch named neighbourhoods and suburbs around the selected city from OSM."""
    if not city or city == SKIP:
        return [SKIP]
    query = quote(", ".join(part for part in (city, region, country) if part))
    found = await _json_request(
        hass,
        f"https://nominatim.openstreetmap.org/search?q={query}&format=jsonv2&limit=1",
    )
    if not isinstance(found, list) or not found:
        return [SKIP]
    try:
        lat, lon = float(found[0]["lat"]), float(found[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return [SKIP]

    overpass_query = (
        "[out:json][timeout:12];("
        f'node(around:15000,{lat},{lon})[place~"^(suburb|neighbourhood|quarter|district)$"];'
        f'way(around:15000,{lat},{lon})[place~"^(suburb|neighbourhood|quarter|district)$"];'
        ");out center tags;"
    )
    result = await _json_request(
        hass,
        "https://overpass-api.de/api/interpreter?data=" + quote(overpass_query),
        timeout=18,
    )
    elements = result.get("elements", []) if isinstance(result, dict) else []
    names = sorted({
        element.get("tags", {}).get("name", "").strip()
        for element in elements
        if element.get("tags", {}).get("name", "").strip()
    })
    return names or [SKIP]


def _dropdown(field, options, default=None):
    """Build a dropdown, retaining a previously saved value if a source omits it."""
    values = list(options or [SKIP])
    if default and default not in values:
        values.append(default)
        values.sort()
    if not default:
        default = values[0]
    marker = vol.Required(field, default=default)
    return marker, selector.SelectSelector(
        selector.SelectSelectorConfig(options=values, mode=selector.SelectSelectorMode.DROPDOWN)
    )


def _location_fields(data):
    """Normalize the hierarchy and preserve the combined location for older consumers."""
    country = data.get("country", "United Kingdom")
    region = data.get("region", "")
    county = data.get("county", "")
    city = data.get("city", "")
    area = data.get("area", "")
    location = ", ".join(
        part for part in (area, city, county, region, country)
        if part and part != SKIP
    )
    return {
        "country": country,
        "region": "" if region == SKIP else region,
        "county": "" if county == SKIP else county,
        "city": "" if city == SKIP else city,
        "area": "" if area == SKIP else area,
        "location": location,
        "ticketmaster_api_key": data.get("ticketmaster_api_key", "").strip(),
    }


def _current_fields(current):
    """Migrate entries that only stored the previous free-text location."""
    region = current.get("region", "")
    county = current.get("county", "")
    city = current.get("city", "")
    area = current.get("area", "")
    old_location = current.get("location", "")
    if old_location and not any((region, county, city, area)):
        city = old_location
    return region, county, city, area


class _LocationFlow:
    """Shared cascading dropdown steps for setup and options."""

    async def _show_country(self, user_input=None):
        if user_input is not None:
            new_country = user_input["country"]
            if new_country != self._location_data.get("country"):
                self._location_data.update({"region": "", "county": SKIP, "city": SKIP, "area": SKIP})
            self._location_data["country"] = new_country
            return await self._show_region()
        countries = await _countries(self.hass)
        marker, field = _dropdown(
            "country", countries, self._location_data.get("country", "United Kingdom")
        )
        return self.async_show_form(
            step_id=self._country_step, data_schema=vol.Schema({marker: field})
        )

    async def _show_region(self, user_input=None):
        if user_input is not None:
            new_region = user_input["region"]
            if new_region != self._location_data.get("region", SKIP):
                self._location_data.update({"county": SKIP, "city": SKIP, "area": SKIP})
            self._location_data["region"] = new_region
            return await self._show_county()
        options = await _regions(self.hass, self._location_data["country"])
        marker, field = _dropdown(
            "region", [SKIP, *[v for v in options if v != SKIP]],
            self._location_data.get("region", SKIP),
        )
        return self.async_show_form(step_id="region", data_schema=vol.Schema({marker: field}))

    async def _show_county(self, user_input=None):
        if user_input is not None:
            new_county = user_input["county"]
            if new_county != self._location_data.get("county", SKIP):
                self._location_data.update({"city": SKIP, "area": SKIP})
            self._location_data["county"] = new_county
            return await self._show_city()
        options = await _counties(
            self.hass, self._location_data["country"], self._location_data.get("region", "")
        )
        marker, field = _dropdown(
            "county", [SKIP, *[v for v in options if v != SKIP]],
            self._location_data.get("county", SKIP),
        )
        return self.async_show_form(step_id="county", data_schema=vol.Schema({marker: field}))

    async def _show_city(self, user_input=None):
        if user_input is not None:
            new_city = user_input["city"]
            if new_city != self._location_data.get("city", SKIP):
                self._location_data["area"] = SKIP
            self._location_data["city"] = new_city
            return await self._show_area()
        options = await _cities(
            self.hass, self._location_data["country"],
            self._location_data.get("region", ""), self._location_data.get("county", SKIP)
        )
        marker, field = _dropdown(
            "city", [SKIP, *[v for v in options if v != SKIP]],
            self._location_data.get("city", SKIP),
        )
        return self.async_show_form(step_id="city", data_schema=vol.Schema({marker: field}))

    async def _show_area(self, user_input=None):
        if user_input is not None:
            self._location_data["area"] = user_input["area"]
            self._location_data["ticketmaster_api_key"] = user_input.get(
                "ticketmaster_api_key", self._location_data.get("ticketmaster_api_key", "")
            ).strip()
            return self._finish_location()
        options = await _areas(
            self.hass, self._location_data["country"],
            self._location_data.get("region", ""), self._location_data.get("city", ""),
        )
        marker, field = _dropdown(
            "area", [SKIP, *[v for v in options if v != SKIP]],
            self._location_data.get("area", SKIP),
        )
        api_marker = vol.Optional(
            "ticketmaster_api_key",
            description={"suggested_value": self._location_data.get("ticketmaster_api_key", "")},
        )
        return self.async_show_form(
            step_id="area",
            data_schema=vol.Schema({marker: field, api_marker: str}),
        )


class ChastityCalendarConfigFlow(_LocationFlow, config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the calendar and event sources."""
    VERSION = 1
    _country_step = "user"

    async def async_step_user(self, user_input=None):
        if not hasattr(self, "_location_data"):
            self._location_data = {"country": "United Kingdom", "ticketmaster_api_key": ""}
        return await self._show_country(user_input)

    async def async_step_region(self, user_input=None):
        return await self._show_region(user_input)

    async def async_step_county(self, user_input=None):
        return await self._show_county(user_input)

    async def async_step_city(self, user_input=None):
        return await self._show_city(user_input)

    async def async_step_area(self, user_input=None):
        return await self._show_area(user_input)

    def _finish_location(self):
        return self.async_create_entry(
            title="Chastity Challenge Calendar", data=_location_fields(self._location_data)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChastityCalendarOptionsFlow(config_entry)


class ChastityCalendarOptionsFlow(_LocationFlow, config_entries.OptionsFlow):
    """Edit discovery preferences."""
    _country_step = "init"

    def __init__(self, config_entry):
        self._config_entry = config_entry
        current = {**config_entry.data, **config_entry.options}
        region, county, city, area = _current_fields(current)
        self._location_data = {
            "country": current.get("country", "United Kingdom"),
            "region": region or SKIP,
            "county": county or SKIP,
            "city": city or SKIP,
            "area": area or SKIP,
            "ticketmaster_api_key": current.get("ticketmaster_api_key", ""),
        }

    async def async_step_init(self, user_input=None):
        return await self._show_country(user_input)

    async def async_step_region(self, user_input=None):
        return await self._show_region(user_input)

    async def async_step_county(self, user_input=None):
        return await self._show_county(user_input)

    async def async_step_city(self, user_input=None):
        return await self._show_city(user_input)

    async def async_step_area(self, user_input=None):
        return await self._show_area(user_input)

    def _finish_location(self):
        return self.async_create_entry(title="", data=_location_fields(self._location_data))
