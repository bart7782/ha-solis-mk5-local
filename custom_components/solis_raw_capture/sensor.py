"""Sensor platform for the Solis Raw Capture debug integration.

Exposes a single entity showing when the last raw packet was captured
and how many bytes it contained, with the full hex dump as an attribute
so it can be copied straight out of the Home Assistant UI (Developer
Tools > States) without needing to dig through the log file.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# Keep attributes small enough to be comfortably stored/displayed.
MAX_HEX_ATTR_LENGTH = 4000


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the raw capture sensor."""
    async_add_entities([RawCaptureSensor(hass, config_entry.entry_id)])


class RawCaptureSensor(SensorEntity):
    """Shows the most recently captured raw packet."""

    should_poll = False
    name = "Solis Raw Capture - Last Packet"
    icon = "mdi:radar"

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_last_packet"
        self._last_capture: dict[str, Any] | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to new-packet events once added to hass."""
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}_packet", self._handle_event))

    @callback
    def _handle_event(self, event) -> None:  # noqa: ANN001
        self._last_capture = event.data
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        if self._last_capture is None:
            return None
        return self._last_capture["timestamp"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._last_capture is None:
            return {"captures_received": 0}
        hex_dump = self._last_capture["hex"]
        return {
            "peer": self._last_capture["peer"],
            "length_bytes": self._last_capture["length"],
            "hex": hex_dump[:MAX_HEX_ATTR_LENGTH],
            "hex_truncated": len(hex_dump) > MAX_HEX_ATTR_LENGTH,
        }
