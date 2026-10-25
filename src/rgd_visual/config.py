"""Physical-device profile is local config, not part of generic driver."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import re
from .protocol import parse_color

REQUIRED_STATES = ("idle", "listening", "thinking", "speaking", "error", "off")
DEFAULT_CONFIG = Path.home() / ".config" / "paky-visual-feedback" / "config.json"


@dataclass(frozen=True)
class VisualState:
    color: str
    brightness: int


@dataclass(frozen=True)
class Settings:
    device_address: str
    states: dict[str, VisualState]


def load(path: Path) -> Settings:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if document.get("adapter") != "miracles-star-ble":
        raise ValueError("Only miracles-star-ble adapter is supported in v0.2")
    mac = document.get("device_address", "")
    if not isinstance(mac, str) or not re.fullmatch(r"[A-Fa-f0-9]{2}(:[A-Fa-f0-9]{2}){5}", mac):
        raise ValueError("Invalid device_address")
    entries = document.get("states")
    if not isinstance(entries, dict):
        raise ValueError("states must be an object")
    states = {}
    for name in REQUIRED_STATES:
        entry = entries.get(name)
        if not isinstance(entry, dict):
            raise ValueError(f"Missing state: {name}")
        color = entry.get("color")
        parse_color(color)
        brightness = entry.get("brightness")
        if type(brightness) is not int or not 0 <= brightness <= 100:
            raise ValueError(f"Invalid brightness for {name}: expected 0..100")
        states[name] = VisualState(color=color.upper(), brightness=brightness)
    return Settings(device_address=mac.upper(), states=states)
