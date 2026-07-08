"""Config flow for the Solis Raw Capture debug integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_PORT, DEFAULT_PORT, DOMAIN

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the raw capture debug tool."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
        return self.async_create_entry(title="Solis Raw Packet Capture", data=user_input)
