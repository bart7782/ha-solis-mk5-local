"""Frame extraction and parsing for the Ginlong/Solis MK5 stick protocol.

The protocol was reverse-engineered from raw captures of a Ginlong stick
logger (hardware GL17-07-261-D, firmware H4.01.51) pushing to a configured
"Remote server" slot. Every ~6 minutes the stick opens a TCP connection and
sends one burst containing two frames:

    68 <len> 51 b0 <logger serial x2> ... <checksum> 16   (103 bytes, data)
    68 <len> 51 b1 <logger serial x2> ... <checksum> 16   (55 bytes, firmware info)

- A frame's total size is <len> + 14 (12 header bytes + checksum + end byte).
- Checksum is the sum of all bytes after the start byte up to (excluding)
  the checksum itself, modulo 256.

Data frame layout (byte offsets from frame start, all values big-endian):

    offset  size  field                    scale  unit
    15      16    inverter serial          ASCII (space padded)
    31      2     inverter temperature     0.1    degC
    33      2     DC voltage string 1      0.1    V
    35      2     DC voltage string 2      0.1    V
    39      2     DC current string 1      0.1    A
    41      2     DC current string 2      0.1    A
    45      2     AC current               0.1    A
    51      2     AC voltage               0.1    V
    57      2     AC frequency             0.01   Hz
    59      2     active power             1      W
    69      2     energy today             0.01   kWh
    71      4     energy total             0.1    kWh

Every field above was validated against at least four captures with the
logger's own web UI as ground truth. Remaining bytes are unknown and are
kept out of the parsed output on purpose.
"""

from __future__ import annotations

import logging
import re

_LOGGER = logging.getLogger(__name__)

FRAME_START = 0x68
FRAME_END = 0x16
# <len> byte counts the payload; header (12) + checksum + end byte make 14.
FRAME_OVERHEAD = 14

CONTROL_DATA = b"\x51\xb0"
CONTROL_INFO = b"\x51\xb1"

DATA_FRAME_SIZE = 103

_MODEL_RE = re.compile(r"\(([^)]+)\)")


def checksum(frame: bytes) -> int:
    """Return the protocol checksum for a complete frame."""
    return sum(frame[1:-2]) & 0xFF


def extract_frames(buffer: bytearray) -> tuple[list[bytes], bytearray]:
    """Split complete, checksum-valid frames off the front of a byte buffer.

    Returns the extracted frames and the remaining (incomplete) buffer.
    Garbage bytes and frames that fail validation are skipped one byte at a
    time so a corrupted stream re-synchronises on the next real frame.
    """
    frames: list[bytes] = []
    # Earliest start byte whose frame is still incomplete; kept in the buffer
    # so it can complete on the next read. A false start byte here (e.g. a
    # garbage 0x68 claiming a huge length) must not block later real frames,
    # so scanning continues past it instead of waiting.
    pending: int | None = None
    i = 0
    while i < len(buffer):
        if buffer[i] != FRAME_START:
            i += 1
            continue
        if len(buffer) - i < 2:
            if pending is None:
                pending = i
            break
        total = buffer[i + 1] + FRAME_OVERHEAD
        if len(buffer) - i < total:
            if pending is None:
                pending = i
            i += 1
            continue
        candidate = bytes(buffer[i : i + total])
        if candidate[-1] != FRAME_END or checksum(candidate) != candidate[-2]:
            i += 1
            continue
        frames.append(candidate)
        # Any incomplete candidate before a validated frame was a false start.
        pending = None
        i += total
    keep_from = pending if pending is not None else i
    return frames, bytearray(buffer[keep_from:])


def _be16(frame: bytes, offset: int) -> int:
    return (frame[offset] << 8) | frame[offset + 1]


def _be32(frame: bytes, offset: int) -> int:
    return int.from_bytes(frame[offset : offset + 4], "big")


def is_data_frame(frame: bytes) -> bool:
    return frame[2:4] == CONTROL_DATA


def is_info_frame(frame: bytes) -> bool:
    return frame[2:4] == CONTROL_INFO


def parse_data_frame(frame: bytes) -> dict[str, float | int | str] | None:
    """Parse a telemetry frame into sensor values.

    Returns None if the frame does not match the known layout or fails the
    plausibility checks, in which case the caller should log the raw hex so
    unknown firmware variants can be reported and added.
    """
    if len(frame) != DATA_FRAME_SIZE:
        return None

    parsed: dict[str, float | int | str] = {
        "serial": frame[15:31].decode("ascii", errors="replace").strip(),
        "temperature": _be16(frame, 31) / 10,
        "dc_voltage_1": _be16(frame, 33) / 10,
        "dc_voltage_2": _be16(frame, 35) / 10,
        "dc_current_1": _be16(frame, 39) / 10,
        "dc_current_2": _be16(frame, 41) / 10,
        "ac_current": _be16(frame, 45) / 10,
        "ac_voltage": _be16(frame, 51) / 10,
        "ac_frequency": _be16(frame, 57) / 100,
        "power": _be16(frame, 59),
        "energy_today": _be16(frame, 69) / 100,
        "energy_total": _be32(frame, 71) / 10,
    }

    # Plausibility limits; a frame from a different firmware layout would
    # produce wild values here, and silently wrong data is worse than none.
    limits = {
        "temperature": (-40, 150),
        "dc_voltage_1": (0, 1000),
        "dc_voltage_2": (0, 1000),
        "dc_current_1": (0, 100),
        "dc_current_2": (0, 100),
        "ac_current": (0, 200),
        "ac_voltage": (0, 500),
        "ac_frequency": (0, 100),
        "power": (0, 50000),
        "energy_today": (0, 1000),
        "energy_total": (0, 10_000_000),
    }
    for key, (low, high) in limits.items():
        value = parsed[key]
        if not low <= value <= high:  # type: ignore[operator]
            _LOGGER.warning(
                "Field %s=%s outside plausible range, dropping frame: %s",
                key,
                value,
                frame.hex(),
            )
            return None
    return parsed


def parse_info_frame(frame: bytes) -> dict[str, str] | None:
    """Parse the firmware/status frame into device info fields.

    The payload is an ASCII blob like "H4.01.51Y4.0.02W1.0.57(GL17-07-261-D)"
    holding the stick firmware versions and the hardware model.
    """
    if len(frame) < FRAME_OVERHEAD + 4:
        return None
    text = frame[14:-4].decode("ascii", errors="replace")
    if not text:
        return None
    info: dict[str, str] = {"firmware": text}
    if match := _MODEL_RE.search(text):
        info["model"] = match.group(1)
        info["firmware"] = text[: match.start()]
    return info
