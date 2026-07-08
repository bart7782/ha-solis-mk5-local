"""The Solis Raw Capture debug integration setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .const import CONF_PORT, DEFAULT_PORT, DOMAIN
from .server import RawCaptureServer

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    captures: list[dict] = []
    hass.data[DOMAIN][entry.entry_id] = {"captures": captures}

    def on_capture(capture: dict) -> None:
        captures.append(capture)
        # Keep only the most recent 50 captures in memory.
        del captures[:-50]
        hass.bus.async_fire(f"{DOMAIN}_packet", capture)

    server = RawCaptureServer(port, on_capture)
    hass.data[DOMAIN][entry.entry_id]["server"] = server
    await server.start_server()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        server: RawCaptureServer | None = data.get("server")
        if server:
            await server.stop_server()
    return unload_ok
