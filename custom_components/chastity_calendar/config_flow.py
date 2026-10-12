"""Config and options flow for Chastity Challenge Calendar."""

import logging

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
    """Fetch a current country list, with a fallback when the service is unavailable."""
    data = await _json_request(
        hass, "https://restcountries.com/v3.1/all?fields=name"
    )
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
    """Fetch states/provinces from CountriesNow."""
    data = await _json_request(
        hass,
        "https://countriesnow.space/api/v0.1/countries/states",
        method="post",
        payload={"country": country},
    )
    states = data.get("data", {}).get("states", []) if isinstance(data, dict) else []
    names = sorted({
        item.get("name", "").strip()
        for item in states
        if isinstance(item, dict) and item.get("name", "").strip()
    })
    return names or [SKIP]


async def _cities(hass, country, region):
    """Fetch cities/towns for a selected country and region."""
    if not region or region == SKIP:
        return [SKIP]
    data = await _json_request(
        hass,
        "https://countriesnow.space/api/v0.1/countries/state/cities",
        method="post",
        payload={"country": country, "state": region},
    )
    cities = data.get("data", []) if isinstance(data, dict) else []
    names = sorted({name.strip() for name in cities if isinstance(name, str) and name.strip()})
    return names or [SKIP]


async def _areas(hass, country, region, city):
    """Find named neighbourhoods and suburbs near a selected city using OpenStreetMap."""
    if not city or city == SKIP:
        return [SKIP]
    query = aiohttp.helpers.quote(city)
    geocode_url = (
        "https://nominatim.openstreetmap.org/search"
        f"?q={query}%2C%20{aiohttp.helpers.quote(region)}%2C%20{aiohttp.helpers.quote(country)}"
        "&format=jsonv2&limit=1"
    )
    found = await _json_request(hass, geocode_url)
    if not isinstance(found, list) or not found:
        return [SKIP]
    try:
        lat, lon = float(found[0]["lat"]), float(found[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return [SKIP]
    overpass_query = (
        "[out:json][timeout:12];("
        f"node(around:15000,{lat},{lon})[place~\"^(suburb|neighbourhood|quarter|district)$\"];"
        f"way(around:15000,{lat},{lon})[place~\"^(suburb|neighbourhood|quarter|district)$\"];"
        ");out center tags;"
    )
    from urllib.parse import quote as url_quote
    result = await _json_request(
        hass,
        "https://overpass-api.de/api/interpreter?data=" + url_quote(overpass_query),
        timeout=18,
    )
    elements = result.get("elements", []) if isinstance(result, dict) else []
    names = sorted({
        element.get("tags", {}).get("name", "").strip()
        for element in elements
        if element.get("tags", {}).get("name", "").strip()
    })
    return names or [SKIP]


def _dropdown(field, options, default=None, required=True):
    """Build a dropdown selector with a safe default."""
    values = options or [SKIP]
    if default not in values:
        default = values[0]
    marker = vol.Required(field, default=default) if required else vol.Optional(field, default=default)
    return marker, selector.SelectSelector(
        selector.SelectSelectorConfig(options=values, mode=selector.SelectSelectorMode.DROPDOWN)
    )


def _api_key_field(default=""):
    return vol.Optional(
        "ticketmaster_api_key",
        description={"suggested_value": default},
    ), str


def _location_fields(data):
    """Normalize the hierarchy and keep the legacy combined location field."""
    country = data.get("country", "United Kingdom")
    region = data.get("region", "")
    city = data.get("city", "")
    area = data.get("area", "")
    location = ", ".join(
        part for part in (area, city, region, country)
        if part and part != SKIP
    )
    return {
        "country": country,
        "region": "" if region == SKIP else region,
        "city": "" if city == SKIP else city,
        "area": "" if area == SKIP else area,
        "location": location,
        "ticketmaster_api_key": data.get("ticketmaster_api_key", "").strip(),
    }


def _current_fields(current):
    """Migrate configurations that only stored the old location field."""
    region = current.get("region", "")
    city = current.get("city", "")
    area = current.get("area", "")
    old_location = current.get("location", "")
    if old_location and not any((region, city, area)):
        city = old_location
    return region, city, area


class _LocationFlow:
    """Shared cascading location steps for setup and options."""

    async def _show_country(self, user_input=None):
        if user_input is not None:
            self._location_data["country"] = user_input["country"]
            self._location_data.update({"region": "", "city": "", "area": ""})
            return await self._show_region()
        countries = await _countries(self.hass)
        marker, field = _dropdown(
            "country", countries, self._location_data.get("country", "United Kingdom")
        )
        return self.async_show_form(
            step_id=self._country_step,
            data_schema=vol.Schema({marker: field}),
        )

    async def _show_region(self, user_input=None):
        if user_input is not None:
            self._location_data["region"] = user_input["region"]
            self._location_data.update({"city": "", "area": ""})
            return await self._show_city()
        options = await _regions(self.hass, self._location_data["country"])
        marker, field = _dropdown("region", [SKIP, *[v for v in options if v != SKIP]], self._location_data.get("region", SKIP))
        return self.async_show_form(step_id="region", data_schema=vol.Schema({marker: field}))

    async def _show_city(self, user_input=None):
        if user_input is not None:
            self._location_data["city"] = user_input["city"]
            self._location_data["area"] = ""
            return await self._show_area()
        options = await _cities(
            self.hass, self._location_data["country"], self._location_data.get("region", "")
        )
        marker, field = _dropdown("city", [SKIP, *[v for v in options if v != SKIP]], self._location_data.get("city", SKIP))
        return self.async_show_form(step_id="city", data_schema=vol.Schema({marker: field}))

    async def _show_area(self, user_input=None):
        if user_input is not None:
            self._location_data["area"] = user_input["area"]
            self._location_data["ticketmaster_api_key"] = user_input.get(
                "ticketmaster_api_key", self._location_data.get("ticketmaster_api_key", "")
            ).strip()
            return self._finish_location()
        options = await _areas(
            self.hass,
            self._location_data["country"],
            self._location_data.get("region", ""),
            self._location_data.get("city", ""),
        )
        marker, field = _dropdown("area", [SKIP, *[v for v in options if v != SKIP]], self._location_data.get("area", SKIP))
        api_marker, api_field = _api_key_field(self._location_data.get("ticketmaster_api_key", ""))
        return self.async_show_form(
            step_id="area",
            data_schema=vol.Schema({marker: field, api_marker: api_field}),
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

    async def async_step_city(self, user_input=None):
        return await self._show_city(user_input)

    async def async_step_area(self, user_input=None):
        return await self._show_area(user_input)

    def _finish_location(self):
        fields = _location_fields(self._location_data)
        return self.async_create_entry(
            title="Chastity Challenge Calendar",
            data=fields,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChastityCalendarOptionsFlow(config_entry)


class ChastityCalendarOptionsFlow(_LocationFlow, config_entries.OptionsFlow):
    """Edit discovery preferences."""
    _country_step = "init"

    def __init__(self, config_entry):
        self.config_entry = config_entry
        current = {**config_entry.data, **config_entry.options}
        region, city, area = _current_fields(current)
        self._location_data = {
            "country": current.get("country", "United Kingdom"),
            "region": region or SKIP,
            "city": city or SKIP,
            "area": area or SKIP,
            "ticketmaster_api_key": current.get("ticketmaster_api_key", ""),
        }

    async def async_step_init(self, user_input=None):
        return await self._show_country(user_input)

    async def async_step_region(self, user_input=None):
        return await self._show_region(user_input)

    async def async_step_city(self, user_input=None):
        return await self._show_city(user_input)

    async def async_step_area(self, user_input=None):
        return await self._show_area(user_input)

    def _finish_location(self):
        return self.async_create_entry(title="", data=_location_fields(self._location_data))
