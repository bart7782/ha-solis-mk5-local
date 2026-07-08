"""TCP server that receives pushed frames from the Ginlong/Solis stick."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from .const import MAX_BUFFER_SIZE
from .protocol import extract_frames

_LOGGER = logging.getLogger(__name__)


class SolisMk5Server:
    """Listens for connections from the stick and emits validated frames.

    The stick opens a fresh connection for every burst, sends its frames and
    may keep the socket open for a while; no response is required. Frames are
    validated (start/end byte + checksum) before being passed on.
    """

    def __init__(self, port: int, on_frame: Callable[[bytes, str], None]) -> None:
        self._port = port
        self._on_frame = on_frame
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start listening; raises OSError if the port cannot be bound."""
        self._server = await asyncio.start_server(
            self._handle_connection, "0.0.0.0", self._port
        )
        _LOGGER.debug("Listening for Solis stick on port %s", self._port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        try:
            await self._server.wait_closed()
        except asyncio.CancelledError:
            pass
        finally:
            self._server = None

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        peer_str = f"{peer[0]}:{peer[1]}" if peer else "unknown"
        _LOGGER.debug("Connection opened from %s", peer_str)
        buffer = bytearray()
        try:
            while True:
                chunk = await reader.read(1024)
                if not chunk:
                    break
                buffer += chunk
                _LOGGER.debug(
                    "Received %d bytes from %s: %s",
                    len(chunk),
                    peer_str,
                    chunk.hex(),
                )
                frames, buffer = extract_frames(buffer)
                for frame in frames:
                    self._on_frame(frame, peer_str)
                if len(buffer) > MAX_BUFFER_SIZE:
                    _LOGGER.warning(
                        "Discarding %d unframeable bytes from %s",
                        len(buffer),
                        peer_str,
                    )
                    buffer.clear()
        except (ConnectionResetError, TimeoutError, OSError) as err:
            _LOGGER.debug("Connection error from %s: %s", peer_str, err)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                pass
            _LOGGER.debug("Connection closed from %s", peer_str)
