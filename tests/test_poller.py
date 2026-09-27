"""Tests for the poller against a fake stick on localhost.

Runs standalone, without Home Assistant (poller.py and protocol.py import
nothing from it):

    python tests/test_poller.py
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

# Load the integration's modules as a package without running its
# __init__.py, which imports Home Assistant.
_PKG = "solis_mk5_local_under_test"
_pkg = types.ModuleType(_PKG)
_pkg.__path__ = [
    str(Path(__file__).resolve().parents[1] / "custom_components" / "solis_mk5_local")
]
sys.modules[_PKG] = _pkg

from importlib import import_module  # noqa: E402

protocol = import_module(f"{_PKG}.protocol")
poller = import_module(f"{_PKG}.poller")
test_protocol = import_module("test_protocol")

SERIAL = test_protocol.LOGGER_SERIAL
REPLY = bytes.fromhex(test_protocol.POLL_REPLY)


async def _fake_stick(reply: bytes | None, chunk: int = 1024, expect=None):
    """Start a fake stick; returns (server, port, list of requests received)."""
    requests: list[bytes] = []

    async def handle(reader, writer):
        request = await reader.read(64)
        requests.append(request)
        if reply is not None and (expect is None or request == expect):
            # The poller hangs up once it has the data frame, so the rest of
            # the reply may hit a closed connection; the real stick copes too.
            try:
                for i in range(0, len(reply), chunk):
                    writer.write(reply[i : i + chunk])
                    await writer.drain()
                    await asyncio.sleep(0)
            except ConnectionError:
                pass
        else:
            await asyncio.sleep(2)  # say nothing, like the busy stick
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1], requests


async def _test_answer() -> None:
    expected = protocol.build_request(SERIAL)
    server, port, requests = await _fake_stick(REPLY, expect=expected)
    async with server:
        frames = await poller.async_request_frames("127.0.0.1", port, SERIAL, 2)
    assert requests == [expected]
    assert any(protocol.is_data_frame(f) for f in frames)
    parsed = protocol.parse_data_frame(next(f for f in frames if protocol.is_data_frame(f)))
    assert parsed["power"] == 3214


async def _test_fragmented_answer() -> None:
    server, port, _ = await _fake_stick(REPLY, chunk=7)
    async with server:
        frames = await poller.async_request_frames("127.0.0.1", port, SERIAL, 2)
    assert any(protocol.is_data_frame(f) for f in frames)


async def _test_silent_stick_times_out() -> None:
    server, port, _ = await _fake_stick(None)
    async with server:
        try:
            await poller.async_request_frames("127.0.0.1", port, SERIAL, 0.5)
        except TimeoutError:
            return
    raise AssertionError("expected TimeoutError")


async def _test_unreachable_raises_oserror() -> None:
    server, port, _ = await _fake_stick(None)
    server.close()
    await server.wait_closed()
    try:
        await poller.async_request_frames("127.0.0.1", port, SERIAL, 1)
    except OSError:
        return
    raise AssertionError("expected OSError")


def test_answer() -> None:
    asyncio.run(_test_answer())


def test_fragmented_answer() -> None:
    asyncio.run(_test_fragmented_answer())


def test_silent_stick_times_out() -> None:
    asyncio.run(_test_silent_stick_times_out())


def test_unreachable_raises_oserror() -> None:
    asyncio.run(_test_unreachable_raises_oserror())


if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f"PASS {name}")
    print("All tests passed.")
