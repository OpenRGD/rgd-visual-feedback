"""Generic, non-actuating eye-expression packs for OpenRGD Visual Feedback.

Packs contain no robot_id and never bind a physical device. The generated
Visual Studio profile is a preview for a requested robot identity only.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from .expressions import validate_expression
from .studio import SCHEMA_V02, validate_profile

PACK_SCHEMA = "openrgd.visual.eye-pack.v0.1-candidate"
_MAX_PACK_BYTES = 128 * 1024
_PACK_ID = re.compile(r"^[a-z][a-z0-9_]{2,47}$")
_EXPR_ID = _PACK_ID
_SCENE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
_EVENT_ID = re.compile(r"^[a-z][a-z0-9._-]{0,99}$")
_ROBOT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_FIELDS = {"schema_version", "pack_id", "revision", "description",
           "expressions", "scene_expressions", "ring_styles", "voice_events"}


def _id(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"Invalid {label}")
    if value in ("constructor", "prototype", "__proto__"):
        raise ValueError(f"Reserved {label}")
    return value


def validate_pack(raw: Any) -> dict:
    """Strictly validate a reusable catalog and all its cross-references."""
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise ValueError("Invalid eye pack fields")
    if raw["schema_version"] != PACK_SCHEMA:
        raise ValueError("Unsupported eye pack schema")
    _id(raw["pack_id"], _PACK_ID, "pack_id")
    if type(raw["revision"]) is not int or raw["revision"] < 1:
        raise ValueError("Invalid revision")
    if not isinstance(raw["description"], str) or not 1 <= len(raw["description"]) <= 200:
        raise ValueError("Invalid description")

    expressions = raw["expressions"]
    if not isinstance(expressions, dict) or not 1 <= len(expressions) <= 32:
        raise ValueError("Expected 1..32 expressions")
    for key, expression in expressions.items():
        _id(key, _EXPR_ID, "expression id")
        validate_expression(expression)
        if key != expression["expression_id"]:
            raise ValueError("Expression identity mismatch")

    scenes = raw["scene_expressions"]
    if not isinstance(scenes, dict) or not 1 <= len(scenes) <= 64:
        raise ValueError("Expected 1..64 scene bindings")
    for scene, expr_id in scenes.items():
        _id(scene, _SCENE_ID, "scene id")
        _id(expr_id, _EXPR_ID, "scene expression id")
        if expr_id not in expressions:
            raise ValueError("Scene references unknown expression")

    rings = raw["ring_styles"]
    if not isinstance(rings, dict) or len(rings) > 64:
        raise ValueError("Invalid preview ring styles")
    for scene, ring in rings.items():
        _id(scene, _SCENE_ID, "ring scene")
        if scene not in scenes:
            raise ValueError("Ring style references unknown scene")
        if not isinstance(ring, dict) or set(ring) != {"color", "brightness"}:
            raise ValueError("Invalid ring style")
        if not isinstance(ring["color"], str) or not _COLOR.fullmatch(ring["color"]):
            raise ValueError("Invalid ring color")
        if type(ring["brightness"]) is not int or not 0 <= ring["brightness"] <= 100:
            raise ValueError("Invalid ring brightness")

    events = raw["voice_events"]
    if not isinstance(events, list) or len(events) > 128:
        raise ValueError("Invalid voice event map")
    seen = set()
    for item in events:
        if not isinstance(item, dict) or set(item) != {"event", "scene", "priority"}:
            raise ValueError("Invalid voice event mapping")
        event = _id(item["event"], _EVENT_ID, "voice event")
        scene = _id(item["scene"], _SCENE_ID, "voice scene")
        priority = item["priority"]
        if type(priority) is not int or not 0 <= priority <= 100:
            raise ValueError("Invalid event priority")
        if scene not in scenes:
            raise ValueError("Event references unknown scene")
        identifier = (event, priority)
        if identifier in seen:
            raise ValueError("Duplicate voice event mapping")
        seen.add(identifier)
    return raw


def load_pack(path: str | Path) -> dict:
    """Read a bounded local JSON file. No network, robot discovery or device writes."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("Eye pack must be a regular file")
    size = p.stat().st_size
    if not 0 < size <= _MAX_PACK_BYTES:
        raise ValueError("Eye pack exceeds size bound or is empty")
    return validate_pack(json.loads(p.read_text(encoding="utf-8")))


def preview_profile(pack: dict, robot_id: str, *, include_ring: bool = True) -> dict:
    """Instantiate a robot-scoped *preview* without creating a hardware binding.

    The caller explicitly chooses the robot ID. The pack itself remains generic.
    Neither device installation nor a catalog approval is performed.
    """
    validate_pack(pack)
    _id(robot_id, _ROBOT_ID, "robot_id")
    if type(include_ring) is not bool:
        raise ValueError("include_ring must be boolean")
    zones = [
        {"id": "expressive-eyes", "label": "Expressive eyes (virtual)",
         "adapter_id": None, "capabilities": ["eye_expression"], "binding_status": "planned"}
    ]
    if include_ring:
        zones.append(
            {"id": "face-ring", "label": "RGB ring (virtual)",
             "adapter_id": None, "capabilities": ["solid"], "binding_status": "planned"}
        )
    scenes = {}
    for scene, expression_id in pack["scene_expressions"].items():
        targets = [{"zone_id": "expressive-eyes", "effect": "eye_expression",
                    "expression_id": expression_id}]
        if include_ring and scene in pack["ring_styles"]:
            ring = pack["ring_styles"][scene]
            targets.append({"zone_id": "face-ring", "effect": "solid",
                            "color": ring["color"], "brightness": ring["brightness"]})
        scenes[scene] = targets
    mappings = [
        {"source": "voice", "event": item["event"], "scene": item["scene"],
         "priority": item["priority"]}
        for item in pack["voice_events"]
    ]
    mappings.extend(
        {"source": "studio-preview", "event": "preview." + scene,
         "scene": scene, "priority": 10}
        for scene in scenes
    )
    profile = {
        "schema_version": SCHEMA_V02,
        "robot_id": robot_id,
        "revision": pack["revision"],
        "zones": zones,
        "scenes": scenes,
        "mappings": mappings,
        "fallback_scene": "connecting" if "connecting" in scenes else next(iter(scenes)),
        "non_actuating": True,
        "preview_only": True,
        "expressions": deepcopy(pack["expressions"]),
    }
    return validate_profile(profile)
