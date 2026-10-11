"""Config and options flow for Chastity Challenge Calendar."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

# Keep these values aligned with the country names understood by discovery.py.
COUNTRIES = [
    "Australia",
    "Austria",
    "Belgium",
    "Brazil",
    "Canada",
    "Denmark",
    "Finland",
    "France",
    "Germany",
    "India",
    "Ireland",
    "Italy",
    "Japan",
    "Mexico",
    "Netherlands",
    "New Zealand",
    "Norway",
    "Portugal",
    "Singapore",
    "South Africa",
    "South Korea",
    "Spain",
    "Sweden",
    "Switzerland",
    "United Kingdom",
    "United States",
]


def _schema(country="United Kingdom", location=""):
    """Build the country dropdown and optional local-area field."""
    if country not in COUNTRIES:
        country = "United Kingdom"
    return vol.Schema({
        vol.Required("country", default=country): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=COUNTRIES,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional("location", default=location): str,
    })


class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the calendar and choose the event search area."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create the calendar entry."""
        if user_input is not None:
            country = user_input["country"].strip()
            location = user_input.get("location", "").strip()
            if country not in COUNTRIES:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_schema(country, location),
                    errors={"country": "required"},
                )
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Chastity Challenge Calendar",
                data={"country": country, "location": location},
            )

        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Allow users to change their search area later."""
        return ChastityCalendarOptionsFlow()


class ChastityCalendarOptionsFlow(config_entries.OptionsFlow):
    """Edit the country and optional local-area search."""

    async def async_step_init(self, user_input=None):
        """Save search preferences."""
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            country = user_input["country"].strip()
            location = user_input.get("location", "").strip()
            if country not in COUNTRIES:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_schema(country, location),
                    errors={"country": "required"},
                )
            return self.async_create_entry(
                title="",
                data={"country": country, "location": location},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                current.get("country", "United Kingdom"),
                current.get("location", ""),
            ),
        )
