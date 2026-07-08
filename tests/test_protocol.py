"""Tests for the frame parser, using real captures from a GL17-07-261-D stick.

Expected values come from the logger's own "Connected Inverter" web page,
noted at capture time. Runs standalone (no pytest needed):

    python tests/test_protocol.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Load protocol.py directly so the test does not need homeassistant installed
# (the package __init__ imports Home Assistant modules).
_spec = importlib.util.spec_from_file_location(
    "protocol",
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solis_mk5_local"
    / "protocol.py",
)
protocol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(protocol)

checksum = protocol.checksum
extract_frames = protocol.extract_frames
is_data_frame = protocol.is_data_frame
is_info_frame = protocol.is_info_frame
parse_data_frame = protocol.parse_data_frame
parse_info_frame = protocol.parse_info_frame

# (burst hex, expected power W, expected energy today kWh, expected total kWh)
CAPTURES = [
    (
        "685951b0b655c824b655c824810105303030333631303135313034303234200153080d07d80000000700070000000c000000000913000000001385011600000000000d0690012200061d0a0000000000000000be360401006a000001d500000000000000003316682951b1b655c824b655c824800148342e30312e353159342e302e303257312e302e353728474c31372d30372d3236312d44290f005a16",
        278, 2.9, 40065.0,
    ),
    (
        "685951b0b655c824b655c824810105303030333631303135313034303234200151079f085a0000000c000a0000001300000000091300000000138801b900000000000d0690012c00061d0a0000000000000000be360401006a000001d500000000000000000416682951b1b655c824b655c824800148342e30312e353159342e302e303257312e302e353728474c31372d30372d3236312d44290f005a16",
        441, 3.0, 40065.0,
    ),
    (
        "685951b0b655c824b655c82481010530303033363130313531303430323420015107da07bc00000011000f0000001b000000000913000000001385027300000000000d0690012c00061d0a0000000000000000be360401006a000001d500000000000000006a16682951b1b655c824b655c824800148342e30312e353159342e302e303257312e302e353728474c31372d30372d3236312d44290a005516",
        627, 3.0, 40065.0,
    ),
    (
        "685951b0b655c824b655c82481010530303033363130313531303430323420015507f808520000001700140000002900000000092600000000138903c000000000000d0690013600061d0a0000000000000000be360401006a000001d50000000000000000ab16682951b1b655c824b655c824800148342e30312e353159342e302e303257312e302e353728474c31372d30372d3236312d44290a005516",
        960, 3.1, 40065.0,
    ),
    (
        "685951b0b655c824b655c82481010530303033363130313531303430323420015b0803080d0000001a00170000002c00000000093000000000138a040a00000000000d0690014000061d0a0000000000000000be360401006a000001d50000000000000000e116682951b1b655c824b655c824800148342e30312e353159342e302e303257312e302e353728474c31372d30372d3236312d44290a005516",
        1034, 3.2, 40065.0,
    ),
    (
        "685951b0b655c824b655c82481010530303033363130313531303430323420015d07ea07cc0000001400110000001f00000000092600000000138702d600000000000d0690014a00061d0a0000000000000000be360401006a000001d500000000000000003516682951b1b655c824b655c824800148342e30312e353159342e302e303257312e302e353728474c31372d30372d3236312d44290f005a16",
        726, 3.3, 40065.0,
    ),
    (
        "685951b0b655c824b655c82481010530303033363130313531303430323420015b080c07ee00000010000d0000001900000000091d000000001387024700000000000d0690014a00061d0a0000000000000000be360401006a000001d50000000000000000d216682951b1b655c824b655c824800148342e30312e353159342e302e303257312e302e353728474c31372d30372d3236312d44290a005516",
        583, 3.3, 40065.0,
    ),
]


def test_full_bursts() -> None:
    for burst_hex, power, today, total in CAPTURES:
        frames, rest = extract_frames(bytearray(bytes.fromhex(burst_hex)))
        assert len(frames) == 2, f"expected 2 frames, got {len(frames)}"
        assert not rest, f"unexpected leftover bytes: {rest.hex()}"

        data_frame, info_frame = frames
        assert is_data_frame(data_frame)
        assert is_info_frame(info_frame)

        parsed = parse_data_frame(data_frame)
        assert parsed is not None
        assert parsed["serial"] == "000361015104024"
        assert parsed["power"] == power
        assert parsed["energy_today"] == today
        assert parsed["energy_total"] == total
        assert 20 <= parsed["temperature"] <= 60
        assert 180 <= parsed["ac_voltage"] <= 260
        assert 49 <= parsed["ac_frequency"] <= 51
        # Cross-check: DC power should roughly match AC power.
        dc_power = (
            parsed["dc_voltage_1"] * parsed["dc_current_1"]
            + parsed["dc_voltage_2"] * parsed["dc_current_2"]
        )
        assert abs(dc_power - power) <= max(60, power * 0.12), (
            f"DC {dc_power:.0f} W vs AC {power} W implausible"
        )

        info = parse_info_frame(info_frame)
        assert info is not None
        assert info["model"] == "GL17-07-261-D"
        assert info["firmware"].startswith("H4.01.51")


def test_fragmented_stream() -> None:
    """Frames must survive arbitrary TCP fragmentation."""
    burst = bytes.fromhex(CAPTURES[0][0])
    for chunk_size in (1, 7, 64, 100):
        buffer = bytearray()
        frames: list[bytes] = []
        for i in range(0, len(burst), chunk_size):
            buffer += burst[i : i + chunk_size]
            new_frames, buffer = extract_frames(buffer)
            frames += new_frames
        assert len(frames) == 2, f"chunk_size={chunk_size}: got {len(frames)} frames"


def test_garbage_and_corruption() -> None:
    burst = bytes.fromhex(CAPTURES[0][0])
    # Leading garbage, including a fake start byte, must be skipped.
    frames, _ = extract_frames(bytearray(b"\x00\x68\xff\x12" + burst))
    assert len(frames) == 2
    # A flipped byte must invalidate exactly that frame (checksum mismatch).
    corrupted = bytearray(burst)
    corrupted[60] ^= 0xFF
    frames, _ = extract_frames(corrupted)
    assert len(frames) == 1  # only the info frame survives


def test_checksum() -> None:
    burst = bytes.fromhex(CAPTURES[0][0])
    frames, _ = extract_frames(bytearray(burst))
    for frame in frames:
        assert checksum(frame) == frame[-2]


def test_wrong_size_data_frame_rejected() -> None:
    burst = bytes.fromhex(CAPTURES[0][0])
    frames, _ = extract_frames(bytearray(burst))
    info_frame = frames[1]
    # The 55-byte info frame is not a valid data frame layout.
    assert parse_data_frame(info_frame) is None


if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f"PASS {name}")
    print("All tests passed.")
