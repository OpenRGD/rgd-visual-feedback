"""Verified Miracles.Star/GATT--DEMO BLE RGB packet subset.

The command BC 04 06 00 00 03 E8 00 00 55 was observed to turn
Paky-01's RGB ring red on 2026-10-25. Colors/brightness were observed
working through the same packet construction. Firmware variants may differ.
"""
from __future__ import annotations

import colorsys
import re

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"


def _packet(command: int, payload: bytes) -> bytes:
    if len(payload) != 6:
        raise ValueError("Expected six-byte payload")
    return bytes((0xBC, command, 0x06)) + payload + b"\x55"


def parse_color(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Color must be #RRGGBB")
    return tuple(bytes.fromhex(value[1:]))  # type: ignore[return-value]


def color_packet(color: str) -> bytes:
    red, green, blue = parse_color(color)
    hue, sat, _ = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    h = max(0, min(360, round(hue * 360)))
    s = max(0, min(1000, round(sat * 1000)))
    return _packet(0x04, bytes((h >> 8, h & 255, s >> 8, s & 255, 0, 0)))


def brightness_packet(percent: int) -> bytes:
    if type(percent) is not int or not 0 <= percent <= 100:
        raise ValueError("Brightness must be an integer between 0 and 100")
    v = percent * 10  # documented protocol range 0..1000
    return _packet(0x05, bytes((v >> 8, v & 255, 0, 0, 0, 0)))
