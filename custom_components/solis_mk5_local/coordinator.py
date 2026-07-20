"""Push-based coordinator holding the latest parsed stick data."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, INCOMPATIBLE_FRAME_THRESHOLD, ISSUE_INCOMPATIBLE_LOGGER
from .protocol import is_data_frame, is_info_frame, parse_data_frame, parse_info_frame
from .server import SolisMk5Server

_LOGGER = logging.getLogger(__name__)


class SolisMk5Coordinator(DataUpdateCoordinator[dict]):
    """Owns the TCP server; data is pushed by the stick, never polled."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        port: int,
        stale_after: timedelta,
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=None
        )
        self.stale_after = stale_after
        self.last_seen: datetime | None = None
        self.server = SolisMk5Server(port, self.handle_frame)
        self._stale_unsub: CALLBACK_TYPE | None = None
        self._consecutive_rejected = 0

    async def _async_update_data(self) -> dict:
        return self.data or {}

    async def async_start(self) -> None:
        await self.server.start()

    async def async_stop(self) -> None:
        if self._stale_unsub:
            self._stale_unsub()
            self._stale_unsub = None
        await self.server.stop()

    @property
    def is_stale(self) -> bool:
        """True when no data frame arrived within the stale window."""
        if self.last_seen is None:
            return True
        return dt_util.utcnow() - self.last_seen > self.stale_after

    @callback
    def handle_frame(self, frame: bytes, peer: str) -> None:
        if is_data_frame(frame):
            parsed = parse_data_frame(frame)
            if parsed is None:
                _LOGGER.warning(
                    "Unrecognised data frame from %s: %s", peer, frame.hex()
                )
                self._consecutive_rejected += 1
                if self._consecutive_rejected >= INCOMPATIBLE_FRAME_THRESHOLD:
                    self._raise_incompatible_logger_issue()
                return
            self._consecutive_rejected = 0
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_INCOMPATIBLE_LOGGER)
            self.last_seen = dt_util.utcnow()
            parsed["last_seen"] = self.last_seen
            parsed["raw_hex"] = frame.hex()
            _LOGGER.debug("Parsed data frame from %s: %s", peer, parsed)
            self.async_set_updated_data({**(self.data or {}), **parsed})
            self._schedule_stale_check()
        elif is_info_frame(frame):
            info = parse_info_frame(frame)
            if info is None:
                _LOGGER.debug("Unparseable info frame from %s: %s", peer, frame.hex())
                return
            _LOGGER.debug("Parsed info frame from %s: %s", peer, info)
            self.async_set_updated_data({**(self.data or {}), **info})
        else:
            _LOGGER.debug(
                "Frame with unknown control code from %s: %s", peer, frame.hex()
            )

    def _raise_incompatible_logger_issue(self) -> None:
        """Surface a Repairs entry when a logger keeps sending unparseable frames.

        A frame that fails checksum/length/plausibility repeatedly, rather than
        occasionally, points at a different logger generation or firmware
        rather than a one-off transmission glitch.
        """
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_INCOMPATIBLE_LOGGER,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_INCOMPATIBLE_LOGGER,
        )

    def _schedule_stale_check(self) -> None:
        """Re-notify entities once the stale window passes with no new data.

        Data is push-only, so without this timer nothing would trigger a
        state update and sensors would show their last value forever.
        """
        if self._stale_unsub:
            self._stale_unsub()

        @callback
        def _notify_stale(_now: datetime) -> None:
            self._stale_unsub = None
            if self.is_stale:
                _LOGGER.debug("No data within stale window; updating entities")
                self.async_update_listeners()

        self._stale_unsub = async_call_later(
            self.hass, self.stale_after.total_seconds() + 5, _notify_stale
        )
