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
    CONF_HOST,
    CONF_LOGGER_SERIAL,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_STALE_AFTER,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_AFTER,
    DOMAIN,
    POLL_PORT,
    POLL_TIMEOUT,
)
from .poller import async_request_frames
from .protocol import is_data_frame, parse_data_frame

PORT_SELECTOR = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
SERIAL_SELECTOR = vol.All(vol.Coerce(int), vol.Range(min=1, max=0xFFFFFFFF))

# The stick does not answer for about 20 seconds after each of its own
# pushes, so one silent try proves nothing. Three tries span that window.
_PROBE_TRIES = 3
_PROBE_PAUSE = 5


async def _stick_answers(host: str, logger_serial: int) -> bool:
    """True when the stick at `host` answers a poll with a valid data frame."""
    for attempt in range(_PROBE_TRIES):
        if attempt:
            await asyncio.sleep(_PROBE_PAUSE)
        try:
            frames = await async_request_frames(
                host, POLL_PORT, logger_serial, POLL_TIMEOUT
            )
        except (OSError, TimeoutError):
            continue
        if any(is_data_frame(f) and parse_data_frame(f) for f in frames):
            return True
    return False


async def _port_is_free(port: int) -> bool:
    try:
        server = await asyncio.start_server(lambda r, w: None, "0.0.0.0", port)
    except OSError:
        return False
    server.close()
    await server.wait_closed()
    return True


class SolisMk5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up with the stick's push, or with its IP address and serial.

    The push (a Remote Server slot on the stick) is optional. With it, the
    integration learns the stick's address and serial by itself. Without it,
    they are asked here and checked with a test poll; they end up in the
    options, where they can be changed later.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT]
            host = (user_input.get(CONF_HOST) or "").strip()
            serial = user_input.get(CONF_LOGGER_SERIAL)
            await self.async_set_unique_id(f"port_{port}")
            self._abort_if_unique_id_configured()
            if not await _port_is_free(port):
                errors[CONF_PORT] = "port_in_use"
            elif bool(host) != bool(serial):
                errors["base"] = "host_and_serial"
            elif host and not await _stick_answers(host, serial):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Solis MK5 Local (port {port})",
                    data={CONF_PORT: port},
                    options={CONF_HOST: host, CONF_LOGGER_SERIAL: serial} if host else {},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_PORT, default=DEFAULT_PORT): PORT_SELECTOR,
                vol.Optional(CONF_HOST): str,
                vol.Optional(CONF_LOGGER_SERIAL): SERIAL_SELECTOR,
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SolisMk5OptionsFlow()


class SolisMk5OptionsFlow(OptionsFlow):
    """Polling, and how long sensors stay fresh without data.

    The stick address is normally learned from its pushes; the host and
    serial fields are only for a stick that does not push to Home Assistant.
    Filling in the host also switches off following the stick to a new
    address, so leave it empty when the push is set up.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if host := (user_input.get(CONF_HOST) or "").strip():
                user_input[CONF_HOST] = host
            else:
                user_input.pop(CONF_HOST, None)
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        coordinator = getattr(self.config_entry, "runtime_data", None)
        learned = coordinator.learned if coordinator else {}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
                    vol.Required(
                        CONF_STALE_AFTER,
                        default=options.get(CONF_STALE_AFTER, DEFAULT_STALE_AFTER),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
                    vol.Optional(
                        CONF_HOST,
                        description={"suggested_value": options.get(CONF_HOST)},
                    ): str,
                    vol.Optional(
                        CONF_LOGGER_SERIAL,
                        description={"suggested_value": options.get(CONF_LOGGER_SERIAL)},
                    ): SERIAL_SELECTOR,
                }
            ),
            description_placeholders={
                "learned_host": learned.get("host") or "-",
                "learned_serial": str(learned.get("logger_serial") or "-"),
            },
        )
