"""Config flow for Chastity Challenge Calendar."""
import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class ChastityCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the local challenge calendar."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create the calendar entry."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Chastity Challenge Calendar",
                data={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
