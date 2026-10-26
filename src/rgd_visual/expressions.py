"""Declarative expressive-eye recipes and cognitive proposal *preview*.

No Python eval/exec, model calls, image generation, BLE, USB, CAN, network,
device discovery, rendering thread, permissions or runtime writes.
This is a reviewable Visual Studio candidate, not a Cognitive integration.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

EXPRESSION_SCHEMA = "openrgd.visual.eye-expression.v0.1-candidate"
PROPOSAL_SCHEMA = "openrgd.visual.cognitive-expression-proposal.v0.1-candidate"
_RENDERER_SCHEMA = "openrgd.visual.eye-frame-plan.v0.1-candidate"
_ID = re.compile(r"^[a-z][a-z0-9_]{2,47}$")
_ROBOT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
_HEX32 = re.compile(r"^[a-f0-9]{32}$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_EYE_FIELDS = {"openness", "gaze_x", "gaze_y", "pupil_scale", "brow_tilt_deg"}
_FIELDS = {
    "schema_version", "expression_id", "label", "origin", "affect", "eyes",
    "palette", "animation", "duration_ms", "preview_only", "non_actuating",
    "claims_emotion_as_internal_state",
}
_PROPOSAL_FIELDS = {
    "contract", "proposal_id", "robot_id", "source_module",
    "source_session_id", "source_sequence", "requested_at_utc",
    "presentation", "approval_required_for_persistence",
    "hardware_execution_authorized", "expression",
}


def _exact(value: Any, fields: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"Invalid {label} fields")
    return value


def _string(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"Invalid {label}")
    return value


def _number(value: Any, low: float, high: float, label: str) -> float:
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError(f"Invalid numeric {label}")
    return float(value)


def _int(value: Any, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Invalid integer {label}")
    return value


def validate_expression(raw: Any) -> dict:
    """Validate exact bounded recipe, with open emotion names / closed primitives."""
    data = _exact(raw, _FIELDS, "expression")
    if data["schema_version"] != EXPRESSION_SCHEMA:
        raise ValueError("Unsupported expression contract")
    _string(data["expression_id"], _ID, "expression id")
    label = data["label"]
    if not isinstance(label, str) or not 1 <= len(label) <= 64 or any(ord(c) < 32 or ord(c) == 127 for c in label):
        raise ValueError("Invalid expression label")
    if data["origin"] not in ("operator", "cognitive_proposal"):
        raise ValueError("Invalid expression origin")
    if (
        data["preview_only"] is not True
        or data["non_actuating"] is not True
        or data["claims_emotion_as_internal_state"] is not False
    ):
        raise ValueError("Expression cannot assert runtime authority or internal emotional states")

    affect = _exact(data["affect"], {"valence", "arousal", "intensity"}, "affect")
    for field, low, high in (("valence", -1, 1), ("arousal", 0, 1), ("intensity", 0, 1)):
        _number(affect[field], low, high, f"affect.{field}")

    eyes = _exact(data["eyes"], {"left", "right"}, "eyes")
    for side in ("left", "right"):
        eye = _exact(eyes[side], _EYE_FIELDS, side)
        for field, low, high in (
            ("openness", 0.12, 1),
            ("gaze_x", -0.6, 0.6),
            ("gaze_y", -0.6, 0.6),
            ("pupil_scale", 0.6, 1.4),
            ("brow_tilt_deg", -20, 20),
        ):
            _number(eye[field], low, high, f"eyes.{side}.{field}")

    palette = _exact(data["palette"], {"background", "iris", "accent", "ring_brightness_pct"}, "palette")
    for field in ("background", "iris", "accent"):
        _string(palette[field], _COLOR, f"palette.{field}")
    _int(palette["ring_brightness_pct"], 0, 40, "ring brightness")

    animation = _exact(data["animation"], {"mode", "blink_interval_ms", "blink_duration_ms"}, "animation")
    if animation["mode"] not in ("still", "breathe", "scan"):
        raise ValueError("Unknown animation primitive")
    _int(animation["blink_interval_ms"], 2500, 12000, "blink interval")
    _int(animation["blink_duration_ms"], 80, 250, "blink duration")
    _int(data["duration_ms"], 500, 12000, "expression duration")
    return data


def validate_proposal(raw: Any) -> dict:
    """Validate untrusted cognitive-sourced candidate without granting authority."""
    data = _exact(raw, _PROPOSAL_FIELDS, "cognitive proposal")
    if data["contract"] != PROPOSAL_SCHEMA:
        raise ValueError("Unsupported cognitive proposal contract")
    _string(data["proposal_id"], _HEX32, "proposal id")
    _string(data["robot_id"], _ROBOT, "robot id")
    if data["source_module"] != "org.openrgd.cognition":
        raise ValueError("Unexpected source module")
    _string(data["source_session_id"], _HEX32, "producer session")
    _int(data["source_sequence"], 0, 2**63 - 1, "source sequence")
    timestamp = data["requested_at_utc"]
    if not isinstance(timestamp, str):
        raise ValueError("Invalid timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include timezone")
    if (
        data["presentation"] != "transient_preview"
        or data["approval_required_for_persistence"] is not True
        or data["hardware_execution_authorized"] is not False
    ):
        raise ValueError("Cognitive proposal cannot authorize hardware or persistent effects")
    validate_expression(data["expression"])
    if data["expression"]["origin"] != "cognitive_proposal":
        raise ValueError("Cognitive proposals must explicitly declare their origin")
    return data


def read_preview(path: str | Path) -> dict:
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 16 * 1024:
        raise ValueError("Preview file missing, symlinked or too large")
    return validate_expression(json.loads(source.read_text(encoding="utf-8")))


def plan_eye_preview(expression: dict) -> dict:
    """Compute display-independent shape intents; never allocate a real framebuffer."""
    expr = validate_expression(expression)
    frame = {}
    for side in ("left", "right"):
        eye = expr["eyes"][side]
        frame[side] = {
            "eye_shape": "ellipse",
            "openness": round(float(eye["openness"]), 3),
            "iris_radius_normalized": round(0.19 * float(eye["pupil_scale"]), 4),
            "gaze_x_normalized": round(float(eye["gaze_x"]), 3),
            "gaze_y_normalized": round(float(eye["gaze_y"]), 3),
            "brow_tilt_deg": round(float(eye["brow_tilt_deg"]), 2),
            "applied": False,
        }
    return {
        "schema_version": _RENDERER_SCHEMA,
        "expression_id": expr["expression_id"],
        "label": expr["label"],
        "robot_identity_claim": None,
        "emotion_internal_state_verified": False,
        "source_kind": expr["origin"],
        "eye_frames": frame,
        "accent_ring_intent": {
            "color": expr["palette"]["accent"].upper(),
            "brightness_pct": expr["palette"]["ring_brightness_pct"],
            "applied": False,
        },
        "palette": {
            "background": expr["palette"]["background"].upper(),
            "iris": expr["palette"]["iris"].upper(),
        },
        "animation": dict(expr["animation"]),
        "duration_ms": expr["duration_ms"],
        "hardware_commands_sent": False,
        "physical_output_observed": False,
        "preview_only": True,
        "non_actuating": True,
    }


def plan_cognitive_proposal(raw: dict) -> dict:
    proposal = validate_proposal(raw)
    plan = plan_eye_preview(proposal["expression"])
    return {
        **plan,
        "proposal_id": proposal["proposal_id"],
        "robot_id": proposal["robot_id"],
        "source_module": proposal["source_module"],
        "approval_required_for_persistence": True,
        "persistence_performed": False,
        "operator_review_status": "pending",
    }
