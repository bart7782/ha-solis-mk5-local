"""
Raw capture TCP server.

This makes NO assumptions whatsoever about the Solis/Solarman/Ginlong
protocol framing (no header parsing, no fixed lengths, no checksums).
It simply accepts a connection, reads whatever bytes arrive until the
peer goes quiet for IDLE_TIMEOUT_SECONDS (or closes the connection),
and logs the complete raw hex dump plus a byte count.

Purpose: capture ground-truth packets from a non-standard/older stick
so an exact parser can be built afterwards from real data, instead of
guessing based on someone else's hardware.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Callable

from .const import IDLE_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class RawCaptureServer:
    """Accepts TCP connections and logs the raw bytes received on each one."""

    def __init__(self, port: int, on_capture: Callable[[dict[str, Any]], None]) -> None:
        self.port = port
        self.on_capture = on_capture
        self._server: asyncio.base_events.Server | None = None

    async def __handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        _LOGGER.info("Connection opened from %s", addr)
        buffer = bytearray()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=IDLE_TIMEOUT_SECONDS)
                except TimeoutError:
                    # No more data for a while - treat this burst as complete.
                    break
                if not chunk:
                    # Peer closed the connection.
                    break
                buffer.extend(chunk)
        except Exception:
            _LOGGER.exception("Error while reading from %s", addr)

        if buffer:
            hex_dump = buffer.hex()
            now = datetime.datetime.now(tz=datetime.UTC).isoformat()
            _LOGGER.info("RAW CAPTURE from %s at %s: %d bytes", addr, now, len(buffer))
            _LOGGER.info("RAW HEX (%d bytes): %s", len(buffer), hex_dump)
            self.on_capture(
                {
                    "peer": str(addr),
                    "timestamp": now,
                    "length": len(buffer),
                    "hex": hex_dump,
                }
            )
        else:
            _LOGGER.info("Connection from %s closed with no data received", addr)

        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001 - best effort cleanup only
            pass

    async def start_server(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self.__handle_connection, "0.0.0.0", self.port)  # noqa: S104
        _LOGGER.info("Solis raw capture server listening on port %s", self.port)

    async def stop_server(self) -> None:
        if self._server is None:
            return
        self._server.close()
        try:
            await self._server.wait_closed()
        except asyncio.CancelledError:
            pass
        finally:
            self._server = None
