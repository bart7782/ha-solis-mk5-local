"""Ask the stick for its current data over TCP.

Plain asyncio on purpose, with no Home Assistant imports, so it can be run
and tested against a real stick without Home Assistant.
"""

from __future__ import annotations

import asyncio
import contextlib

from .protocol import build_request, extract_frames, is_data_frame

# Enough for a data frame plus the acknowledgement frame that follows it.
_MAX_REPLY = 4096


async def async_request_frames(
    host: str, port: int, logger_serial: int, timeout: float
) -> list[bytes]:
    """Send one data request and return the valid frames of the reply.

    Opens a fresh connection per request, the way the stick expects it.
    Returns once a data frame has arrived or the stick closes the connection.
    Raises OSError when the stick cannot be reached and TimeoutError when it
    does not answer within `timeout` seconds.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout
    )
    try:
        writer.write(build_request(logger_serial))
        await writer.drain()
        buffer = bytearray()
        frames: list[bytes] = []
        while not any(is_data_frame(frame) for frame in frames):
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError
            chunk = await asyncio.wait_for(reader.read(1024), remaining)
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > _MAX_REPLY:
                break
            new_frames, buffer = extract_frames(buffer)
            frames += new_frames
        return frames
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
