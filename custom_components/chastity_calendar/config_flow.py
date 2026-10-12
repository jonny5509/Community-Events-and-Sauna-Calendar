"""Config and options flow for Chastity Challenge Calendar."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

COUNTRIES = [
    "Australia", "Austria", "Belgium", "Brazil", "Canada", "Denmark",
    "Finland", "France", "Germany", "India", "Ireland", "Italy", "Japan",
    "Mexico", "Netherlands", "New Zealand", "Norway", "Portugal", "Singapore",
    "South Africa", "South Korea", "Spain", "Sweden", "Switzerland",
    "United Kingdom", "United States",
]


def _schema(country="United Kingdom", region="", city="", area="", ticketmaster_api_key=""):
    """Build a location hierarchy from broad to specific."""
    if country not in COUNTRIES:
        country = "United Kingdom"
    return vol.Schema({
        vol.Required("country", default=country): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=COUNTRIES,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional("region", default=region): str,
        vol.Optional("city", default=city): str,
        vol.Optional("area", default=area): str,
        vol.Optional("ticketmaster_api_key", description={"suggested_value": ticketmaster_api_key}): str,
    })


def _location_fields(user_input):
    """Normalize hierarchical location fields and create the combined search area."""
    region = user_input.get("region", "").strip()
    city = user_input.get("city", "").strip()
    area = user_input.get("area", "").strip()
    location = ", ".join(part for part in (area, city, region) if part)
    return {"region": region, "city": city, "area": area, "location": location}


def _current_fields(current):
    """Read new hierarchical options and gracefully migrate the old location field."""
    region = current.get("region", "")
    city = current.get("city", "")
    area = current.get("area", "")
    old_location = current.get("location", "")
    if old_location and not any((region, city, area)):
        city = old_location
    return region, city, area


class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the calendar and event sources."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create integration entry."""
        if user_input is not None:
            country = user_input["country"].strip()
            api_key = user_input.get("ticketmaster_api_key", "").strip()
            fields = _location_fields(user_input)
            if country not in COUNTRIES:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_schema(country, fields["region"], fields["city"], fields["area"], api_key),
                    errors={"country": "required"},
                )
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Chastity Challenge Calendar",
                data={"country": country, **fields, "ticketmaster_api_key": api_key},
            )
        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Allow users to change search preferences."""
        return ChastityCalendarOptionsFlow()


class ChastityCalendarOptionsFlow(config_entries.OptionsFlow):
    """Edit discovery preferences."""

    async def async_step_init(self, user_input=None):
        """Save preferences."""
        current = {**self.config_entry.data, **self.config_entry.options}
        region, city, area = _current_fields(current)
        if user_input is not None:
            country = user_input["country"].strip()
            api_key = user_input.get("ticketmaster_api_key", "").strip()
            fields = _location_fields(user_input)
            if country not in COUNTRIES:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_schema(country, fields["region"], fields["city"], fields["area"], api_key),
                    errors={"country": "required"},
                )
            return self.async_create_entry(
                title="",
                data={"country": country, **fields, "ticketmaster_api_key": api_key},
            )
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                current.get("country", "United Kingdom"),
                region,
                city,
                area,
                current.get("ticketmaster_api_key", ""),
            ),
        )
