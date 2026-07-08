"""Solis MK5 Local: local push integration for Ginlong/Solis stick loggers."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_PORT, CONF_STALE_AFTER, DEFAULT_STALE_AFTER, DOMAIN, PLATFORMS
from .coordinator import SolisMk5Coordinator

_LOGGER = logging.getLogger(__name__)

type SolisMk5ConfigEntry = ConfigEntry[SolisMk5Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SolisMk5ConfigEntry) -> bool:
    port: int = entry.data[CONF_PORT]
    stale_minutes: int = entry.options.get(CONF_STALE_AFTER, DEFAULT_STALE_AFTER)

    coordinator = SolisMk5Coordinator(
        hass, entry, port, timedelta(minutes=stale_minutes)
    )
    try:
        await coordinator.async_start()
    except OSError as err:
        raise ConfigEntryNotReady(f"Cannot listen on TCP port {port}: {err}") from err

    entry.runtime_data = coordinator

    # Register the device up front so entities exist right after a restart
    # (before the stick's first push); enrich it once real data arrives.
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Solis / Ginlong",
        name="Solis inverter",
    )

    @callback
    def _enrich_device() -> None:
        data = coordinator.data or {}
        updates: dict[str, str] = {}
        if serial := data.get("serial"):
            updates["serial_number"] = serial
        if model := data.get("model"):
            updates["model"] = model
        if firmware := data.get("firmware"):
            updates["sw_version"] = firmware
        if updates:
            device_registry.async_update_device(device.id, **updates)

    entry.async_on_unload(coordinator.async_add_listener(_enrich_device))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolisMk5ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options (port, stale window) change."""
    await hass.config_entries.async_reload(entry.entry_id)
