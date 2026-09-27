"""Diagnostics download: settings, poll health and the last raw frame."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SolisMk5ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolisMk5ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    return {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "learned_from_push": coordinator.learned,
        "poll_target": coordinator.poll_target,
        "scan_interval": coordinator.scan_interval,
        "poll_stats": dict(coordinator.poll_stats),
        "last_seen": coordinator.last_seen.isoformat() if coordinator.last_seen else None,
        "last_source": coordinator.last_source,
        "live": coordinator.is_live,
        "stale": coordinator.is_stale,
        "last_data_frame_hex": data.get("raw_hex"),
        "firmware": data.get("firmware"),
        "model": data.get("model"),
    }
