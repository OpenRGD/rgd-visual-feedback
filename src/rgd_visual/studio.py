"""Visual Effects Studio — deterministic, OFFLINE, read-only scene preview.

This module never connects to BLE, MQTT, USB, CAN, the Console, or an actuator.
It is only a portable editor/contract preview. Real routing, concurrency,
host permissions and output verification require separately reviewed waves.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "openrgd.visual-studio.profile.v0.1-candidate"
EFFECTS = frozenset({"solid", "pulse", "chase", "wave"})
_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
_EVENT = re.compile(r"^[a-z][a-z0-9._-]{0,99}$")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_TOP = {"schema_version", "robot_id", "revision", "zones", "scenes",
        "mappings", "fallback_scene", "non_actuating", "preview_only"}


def _object(value: Any, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Invalid {label} object fields")
    return value


def _identifier(value: Any, label: str, pattern: re.Pattern[str] = _NAME) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"Invalid {label}")
    return value


def _array(value: Any, limit: int, label: str, *, nonempty: bool = False) -> list:
    if not isinstance(value, list) or len(value) > limit or (nonempty and not value):
        raise ValueError(f"Invalid {label}")
    return value


def validate_profile(raw: Any) -> dict:
    """Validate the candidate preview subset without optional JSON-schema deps."""
    p = _object(raw, _TOP, "profile")
    if p["schema_version"] != SCHEMA or p["non_actuating"] is not True or p["preview_only"] is not True:
        raise ValueError("Unsupported or potentially actuating Visual Studio profile")
    _identifier(p["robot_id"], "robot_id")
    if type(p["revision"]) is not int or p["revision"] < 1:
        raise ValueError("Invalid revision")

    zones = _array(p["zones"], 32, "zones", nonempty=True)
    zone_by_id = {}
    for zone in zones:
        _object(zone, {"id", "label", "adapter_id", "capabilities", "binding_status"}, "zone")
        zone_id = _identifier(zone["id"], "zone.id")
        if zone_id in zone_by_id:
            raise ValueError("Duplicate zone id")
        if not isinstance(zone["label"], str) or not 1 <= len(zone["label"]) <= 120:
            raise ValueError("Invalid zone label")
        adapter_id = zone["adapter_id"]
        if adapter_id is not None and (not isinstance(adapter_id, str) or not _EVENT.fullmatch(adapter_id)):
            raise ValueError("Invalid zone adapter_id")
        capabilities = _array(zone["capabilities"], 12, "zone.capabilities", nonempty=True)
        if any(v not in EFFECTS for v in capabilities) or len(set(capabilities)) != len(capabilities):
            raise ValueError("Unknown or duplicate zone capability")
        if zone["binding_status"] not in ("planned", "operator_reported"):
            raise ValueError("Unknown zone binding_status")
        if zone["binding_status"] == "planned" and adapter_id is not None:
            # This stage intentionally has no real device bindings.
            raise ValueError("A planned zone cannot claim an adapter binding")
        zone_by_id[zone_id] = zone

    scenes = p["scenes"]
    if not isinstance(scenes, dict) or not 1 <= len(scenes) <= 64:
        raise ValueError("Invalid scenes")
    for name, targets in scenes.items():
        _identifier(name, "scene name")
        _array(targets, 32, "scene targets", nonempty=True)
        used = set()
        for target in targets:
            _object(target, {"zone_id", "effect", "color", "brightness"}, "scene output intent")
            zone_id = _identifier(target["zone_id"], "scene zone id")
            if zone_id not in zone_by_id or zone_id in used:
                raise ValueError("Missing or duplicate zone reference in scene")
            used.add(zone_id)
            if target["effect"] not in EFFECTS:
                raise ValueError("Unknown scene effect")
            if not isinstance(target["color"], str) or not _HEX.fullmatch(target["color"]):
                raise ValueError("Invalid color #RRGGBB")
            if type(target["brightness"]) is not int or not 0 <= target["brightness"] <= 100:
                raise ValueError("Invalid brightness")
    if p["fallback_scene"] not in scenes:
        raise ValueError("Fallback scene not defined")

    mappings = _array(p["mappings"], 128, "mappings")
    seen = set()
    for mapping in mappings:
        _object(mapping, {"source", "event", "scene", "priority"}, "mapping")
        source = _identifier(mapping["source"], "mapping source")
        event = _identifier(mapping["event"], "mapping event", _EVENT)
        if mapping["scene"] not in scenes:
            raise ValueError("Mapping refers to nonexistent scene")
        if type(mapping["priority"]) is not int or not 0 <= mapping["priority"] <= 100:
            raise ValueError("Invalid mapping priority")
        key = (source, event, mapping["priority"])
        if key in seen:
            raise ValueError("Ambiguous mapping with equal priority")
        seen.add(key)
    return p


def load_profile(path: str | Path) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
        raise ValueError("Invalid or too large profile")
    return validate_profile(json.loads(path.read_text(encoding="utf-8")))


def preview(profile: dict, source: str, event: str) -> dict:
    """Return selected, hypothetical scene; not a hardware dispatch."""
    p = validate_profile(profile)
    _identifier(source, "source")
    _identifier(event, "event", _EVENT)
    candidates = [row for row in p["mappings"] if row["source"] == source and row["event"] == event]
    matched = max(candidates, key=lambda row: row["priority"]) if candidates else None
    scene_name = matched["scene"] if matched else p["fallback_scene"]
    zones = {z["id"]: z for z in p["zones"]}
    outputs = []
    for target in p["scenes"][scene_name]:
        zone = zones[target["zone_id"]]
        declared = target["effect"] in zone["capabilities"]
        outputs.append({
            "zone_id": target["zone_id"],
            "zone_label": zone["label"],
            "adapter_id": zone["adapter_id"],
            "binding_status": zone["binding_status"],
            "effect": target["effect"],
            "color": target["color"].upper(),
            "brightness": target["brightness"],
            "eligible_by_declared_capabilities": declared and zone["binding_status"] == "operator_reported",
            "applied": False,
            "physical_light_observed": False,
            "reason": "preview_only" if declared and zone["binding_status"] == "operator_reported"
                      else "planned_zone" if zone["binding_status"] == "planned"
                      else "effect_not_supported_by_declared_zone",
        })
    return {
        "schema_version": "openrgd.visual-studio.preview.v0.1-candidate",
        "robot_id": p["robot_id"],
        "source": source,
        "event": event,
        "matched": matched is not None,
        "priority": matched["priority"] if matched else None,
        "scene": scene_name,
        "outputs": outputs,
        "preview_only": True,
        "non_actuating": True,
        "hardware_commands_sent": False,
    }
