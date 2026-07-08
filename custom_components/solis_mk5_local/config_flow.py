"""Config flow for the Solis MK5 Local integration."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_PORT,
    CONF_STALE_AFTER,
    DEFAULT_PORT,
    DEFAULT_STALE_AFTER,
    DOMAIN,
)

PORT_SELECTOR = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))


async def _port_is_free(port: int) -> bool:
    try:
        server = await asyncio.start_server(lambda r, w: None, "0.0.0.0", port)
    except OSError:
        return False
    server.close()
    await server.wait_closed()
    return True


class SolisMk5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the TCP port the stick's Remote Server slot points at."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"port_{port}")
            self._abort_if_unique_id_configured()
            if not await _port_is_free(port):
                errors[CONF_PORT] = "port_in_use"
            else:
                return self.async_create_entry(
                    title=f"Solis MK5 Local (poort {port})", data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_PORT, default=DEFAULT_PORT): PORT_SELECTOR}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SolisMk5OptionsFlow()


class SolisMk5OptionsFlow(OptionsFlow):
    """Let the user tune how long sensors stay fresh without data."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STALE_AFTER,
                        default=self.config_entry.options.get(
                            CONF_STALE_AFTER, DEFAULT_STALE_AFTER
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
                }
            ),
        )
