"""Best-effort nearby sauna discovery using OpenStreetMap."""
from __future__ import annotations

import logging
import math
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_REFRESH = timedelta(hours=24)
_USER_AGENT = "HomeAssistant-ChastityCalendar/1.5 (OpenStreetMap sauna discovery)"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometres."""
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))


class NearbySaunasSensor(SensorEntity):
    """List public sauna and bath locations near the configured city/region."""

    _attr_has_entity_name = True
    _attr_name = "Nearby Saunas"
    _attr_icon = "mdi:hot-tub"
    _attr_native_unit_of_measurement = None

    def __init__(self, hass, country: str, location: str, geocode_location: str | None = None) -> None:
        self.hass = hass
        self.country = country.strip()
        self.location = location.strip()
        # Prefer a precise area/city query for geocoding. The full hierarchy is
        # retained separately for display and event-search context.
        self.geocode_location = (geocode_location or location).strip()
        self._places: list[dict] = []
        self._error: str | None = None
        self._updated: str | None = None
        self._attr_unique_id = f"{DOMAIN}_nearby_saunas"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_refresh()
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_refresh, _REFRESH)
        )

    async def _async_refresh(self, _now=None) -> None:
        """Geocode configured area and query nearby OpenStreetMap sauna features."""
        if not self.geocode_location:
            self._error = "Set a city or region in the integration options to find nearby saunas."
            self._places = []
            self.async_write_ha_state()
            return
        session = async_get_clientsession(self.hass)
        query = ", ".join(part for part in (self.geocode_location, self.country) if part)
        headers = {"User-Agent": _USER_AGENT}
        try:
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "jsonv2", "limit": "1"},
                headers=headers,
                timeout=20,
            ) as response:
                response.raise_for_status()
                geocoded = await response.json()
            if not geocoded:
                self._places = []
                self._error = f"Could not locate configured area: {query}"
                self.async_write_ha_state()
                return
            lat, lon = float(geocoded[0]["lat"]), float(geocoded[0]["lon"])
            # A 20 km radius is a useful default for nearby facilities.
            overpass_query = f"""[out:json][timeout:25];
(
  node(around:20000,{lat},{lon})[leisure=sauna];
  way(around:20000,{lat},{lon})[leisure=sauna];
  relation(around:20000,{lat},{lon})[leisure=sauna];
  node(around:20000,{lat},{lon})[amenity=public_bath];
  way(around:20000,{lat},{lon})[amenity=public_bath];
  relation(around:20000,{lat},{lon})[amenity=public_bath];
);
out center tags;"""
            async with session.post(
                "https://overpass-api.de/api/interpreter",
                data=overpass_query,
                headers=headers,
                timeout=35,
            ) as response:
                response.raise_for_status()
                payload = await response.json()
            places = []
            seen = set()
            for element in payload.get("elements", []):
                tags = element.get("tags", {})
                name = tags.get("name") or tags.get("name:en")
                if not name:
                    continue
                key = (name.casefold(), tags.get("addr:street", ""), tags.get("addr:housenumber", ""))
                if key in seen:
                    continue
                seen.add(key)
                center = element.get("center", element)
                if "lat" not in center or "lon" not in center:
                    continue
                place_lat, place_lon = float(center["lat"]), float(center["lon"])
                address = " ".join(
                    part for part in (
                        tags.get("addr:housenumber"),
                        tags.get("addr:street"),
                        tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:suburb"),
                        tags.get("addr:postcode"),
                    ) if part
                )
                places.append({
                    "name": name,
                    "type": "sauna" if tags.get("leisure") == "sauna" else "public bath",
                    "address": address or "Address not listed in OpenStreetMap",
                    "distance_km": round(_distance_km(lat, lon, place_lat, place_lon), 1),
                    "latitude": place_lat,
                    "longitude": place_lon,
                    "website": tags.get("website") or tags.get("contact:website") or "",
                    "osm_url": f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}",
                })
            self._places = sorted(places, key=lambda place: place["distance_km"])
            self._error = None
            from homeassistant.util import dt as dt_util
            self._updated = dt_util.now().isoformat()
        except Exception as err:
            _LOGGER.warning("Nearby sauna lookup failed: %s", err)
            self._error = "Sauna search temporarily unavailable; results may be stale."
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Expose the number of mapped nearby places."""
        return len(self._places)

    @property
    def extra_state_attributes(self) -> dict:
        """Expose nearest-first place details for dashboards and automations."""
        return {
            "search_area": ", ".join(part for part in (self.location, self.country) if part),
            "radius_km": 20,
            "count": len(self._places),
            "saunas": self._places,
            "last_updated": self._updated,
            "note": "Best-effort OpenStreetMap data. Adult-only facilities and events may be missing or incorrectly tagged; confirm opening hours, age restrictions and access directly with each venue.",
            "error": self._error,
        }
