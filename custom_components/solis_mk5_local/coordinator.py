"""Coordinator holding the latest stick data, from polls and from pushes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    BACKOFF_AFTER_FAILURES,
    BACKOFF_INTERVAL,
    DOMAIN,
    INCOMPATIBLE_FRAME_THRESHOLD,
    ISSUE_INCOMPATIBLE_LOGGER,
    LIVE_WINDOW_MIN,
    POLL_PORT,
    POLL_TIMEOUT,
    STORAGE_VERSION,
)
from .poller import async_request_frames
from .protocol import (
    is_data_frame,
    is_info_frame,
    logger_serial_from_frame,
    parse_data_frame,
    parse_info_frame,
)
from .server import SolisMk5Server

_LOGGER = logging.getLogger(__name__)

SOURCE_POLL = "poll"
SOURCE_PUSH = "push"


class SolisMk5Coordinator(DataUpdateCoordinator[dict]):
    """Owns the TCP listener and the poll loop; both feed the same data.

    Polling is the main source once the stick's address is known. The push
    stays as a fallback, and is how that address is learned: every push
    carries the logger serial and arrives from the stick's current IP
    address. A stick that moves to another address is found again at its
    next push, without any configuration.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        port: int,
        stale_after: timedelta,
        scan_interval: int,
        host_override: str | None,
        serial_override: int | None,
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=None
        )
        self.stale_after = stale_after
        self.scan_interval = scan_interval
        self.live_window = timedelta(seconds=max(LIVE_WINDOW_MIN, 3 * scan_interval))
        self.last_seen: datetime | None = None
        self.last_source: str | None = None
        self.server = SolisMk5Server(port, self.handle_frame)
        self._host_override = host_override
        self._serial_override = serial_override
        self._learned: dict[str, Any] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._stale_unsub: CALLBACK_TYPE | None = None
        self._live_unsub: CALLBACK_TYPE | None = None
        self._consecutive_rejected = 0
        self._wake = asyncio.Event()
        self._poll_failures = 0
        self.poll_stats: dict[str, Any] = {
            "answered": 0,
            "unanswered": 0,
            "last_error": None,
            "backing_off": False,
        }

    async def _async_update_data(self) -> dict:
        return self.data or {}

    # --- lifecycle -------------------------------------------------------

    async def async_start(self) -> None:
        self._learned = await self._store.async_load() or {}
        await self.server.start()
        if self.scan_interval:
            self.config_entry.async_create_background_task(
                self.hass, self._poll_loop(), f"{DOMAIN} poll loop"
            )

    async def async_stop(self) -> None:
        for unsub in (self._stale_unsub, self._live_unsub):
            if unsub:
                unsub()
        self._stale_unsub = self._live_unsub = None
        await self.server.stop()

    # --- state -----------------------------------------------------------

    @property
    def is_stale(self) -> bool:
        """True when no data frame arrived within the stale window."""
        if self.last_seen is None:
            return True
        return dt_util.utcnow() - self.last_seen > self.stale_after

    @property
    def is_live(self) -> bool:
        """True when the newest data frame is recent enough to act on."""
        if self.last_seen is None:
            return False
        return dt_util.utcnow() - self.last_seen <= self.live_window

    @property
    def poll_target(self) -> tuple[str, int] | None:
        """Where to poll, and with which serial.

        Host: the configured one if set, else the address pushes come from.
        Serial: the one the stick itself reported in its last push or poll
        answer, else the configured one. The configured serial is only
        needed for the very first request; after that the stick's own
        number wins, so a typo cannot stick.
        """
        host = self._host_override or self._learned.get("host")
        serial = self._learned.get("logger_serial") or self._serial_override
        if host and serial:
            return host, int(serial)
        return None

    @property
    def learned(self) -> dict[str, Any]:
        return dict(self._learned)

    # --- incoming frames -------------------------------------------------

    @callback
    def handle_frame(
        self, frame: bytes, peer: str, source: str = SOURCE_PUSH
    ) -> bool:
        """Process one validated frame. Returns True for an accepted data frame."""
        if is_data_frame(frame):
            parsed = parse_data_frame(frame)
            if parsed is None:
                _LOGGER.warning(
                    "Unrecognised data frame from %s: %s", peer, frame.hex()
                )
                self._consecutive_rejected += 1
                if self._consecutive_rejected >= INCOMPATIBLE_FRAME_THRESHOLD:
                    self._raise_incompatible_logger_issue()
                return False
            self._consecutive_rejected = 0
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_INCOMPATIBLE_LOGGER)
            self._learn(frame, peer, source)
            self.last_seen = dt_util.utcnow()
            self.last_source = source
            parsed["last_seen"] = self.last_seen
            parsed["raw_hex"] = frame.hex()
            _LOGGER.debug("Parsed data frame (%s) from %s: %s", source, peer, parsed)
            self.async_set_updated_data({**(self.data or {}), **parsed})
            self._schedule_stale_check()
            self._schedule_live_check()
            # Any frame ends a night-time back-off: the stick is awake again.
            if self._poll_failures:
                self._wake.set()
            return True
        if is_info_frame(frame):
            info = parse_info_frame(frame)
            if info is None:
                _LOGGER.debug("Unparseable info frame from %s: %s", peer, frame.hex())
                return False
            _LOGGER.debug("Parsed info frame from %s: %s", peer, info)
            self.async_set_updated_data({**(self.data or {}), **info})
            return False
        _LOGGER.debug("Frame with unknown control code from %s: %s", peer, frame.hex())
        return False

    @callback
    def _learn(self, frame: bytes, peer: str, source: str) -> None:
        """Remember the stick's serial, and from a push also its address."""
        learned = dict(self._learned)
        if serial := logger_serial_from_frame(frame):
            learned["logger_serial"] = serial
        if source == SOURCE_PUSH and ":" in peer:
            learned["host"] = peer.rsplit(":", 1)[0]
        if learned == self._learned:
            return
        _LOGGER.info(
            "Stick %s at %s (learned from a %s)",
            learned.get("logger_serial"),
            learned.get("host") or self._host_override,
            source,
        )
        self._learned = learned
        self._store.async_delay_save(lambda: self._learned, 1)
        self._wake.set()

    # --- polling ---------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Poll the stick until the entry unloads (which cancels this task)."""
        loop = asyncio.get_running_loop()
        while True:
            started = loop.time()
            if (target := self.poll_target) is not None:
                await self._poll_once(*target)
            if target is None or self._poll_failures >= BACKOFF_AFTER_FAILURES:
                # Nothing to poll yet, or the stick is off for the night. A
                # push (which teaches the address, or means the stick is back)
                # wakes the loop early.
                delay = BACKOFF_INTERVAL
            else:
                delay = self.scan_interval
            self._wake.clear()
            try:
                await asyncio.wait_for(
                    self._wake.wait(), max(0.0, delay - (loop.time() - started))
                )
            except TimeoutError:
                pass

    async def _poll_once(self, host: str, serial: int) -> None:
        try:
            frames = await async_request_frames(host, POLL_PORT, serial, POLL_TIMEOUT)
        except (OSError, TimeoutError) as err:
            self._poll_result(False, type(err).__name__ + (f": {err}" if str(err) else ""))
            return
        accepted = False
        for frame in frames:
            accepted |= self.handle_frame(frame, f"{host}:{POLL_PORT}", SOURCE_POLL)
        self._poll_result(accepted, None if accepted else "no data frame in reply")

    @callback
    def _poll_result(self, answered: bool, error: str | None) -> None:
        stats = self.poll_stats
        if answered:
            stats["answered"] += 1
            if stats["backing_off"]:
                _LOGGER.info("Stick answers polls again")
            stats["backing_off"] = False
            self._poll_failures = 0
            return
        stats["unanswered"] += 1
        stats["last_error"] = error
        self._poll_failures += 1
        if self._poll_failures == BACKOFF_AFTER_FAILURES:
            stats["backing_off"] = True
            # Normal every evening: the stick switches off with the inverter.
            _LOGGER.info(
                "Stick not answering polls (%s); polling every %s s until it is back",
                error,
                BACKOFF_INTERVAL,
            )

    # --- repairs and timers ----------------------------------------------

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

        Without this timer nothing would trigger a state update once the
        stick goes quiet, and sensors would show their last value forever.
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

    def _schedule_live_check(self) -> None:
        """Re-notify entities when the live window passes with no new data."""
        if self._live_unsub:
            self._live_unsub()

        @callback
        def _notify_not_live(_now: datetime) -> None:
            self._live_unsub = None
            if not self.is_live:
                self.async_update_listeners()

        self._live_unsub = async_call_later(
            self.hass, self.live_window.total_seconds() + 1, _notify_not_live
        )
