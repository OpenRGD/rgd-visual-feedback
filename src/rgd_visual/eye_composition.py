"""Eye compositor — deterministic, non-actuating visual-policy *preview* v0.1.

Implements a strict subset of the Paky-01 eyes behavioral design as a generic
robot-independent function. Input facts are intentionally SYNTHETIC and do not
authenticate Voice, PERIPH, microphone, gaze or playback; there is no live
ingress or persistent arbiter in this module. No BLE/USB/CAN/display access.

Functional state wins over social gestures. Current gaze wins over decorative
eye gaze. The functional ring palette never follows a temporary social gesture.
Stale facts fail to a non-listening/non-speaking neutral preview.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .expression_packs import validate_pack
from .expressions import plan_eye_preview, validate_expression

SCHEMA = "openrgd.visual.eye-compose-input.v0.1-candidate"
OUTPUT_SCHEMA = "openrgd.visual.eye-compose-result.v0.1-candidate"
_ROBOT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
_GESTURE_ID = re.compile(r"^[a-f0-9]{32}$")
PHASES = frozenset({
    "idle", "listening", "thinking", "speaking", "error", "off",
    "boot", "connecting", "transcribing", "awaiting_user",
    "no_input", "link_lost", "rest",
})
SOCIAL = frozenset({
    "welcome", "friendly", "curious", "surprised", "uncertain", "ack", "concern",
})
SOCIAL_ALLOWED = {
    "idle": SOCIAL,
    "speaking": frozenset({"friendly", "surprised", "concern"}),
    "listening": frozenset({"ack"}),
    "awaiting_user": frozenset({"curious"}),
}
VOICE_STALE_MS = 2000
GAZE_STALE_MS = 700
MIC_STALE_MS = 2000
_PLAYBACK_STATES = frozenset({"speaking"})
_LOCKED = frozenset({"error", "off", "boot", "connecting", "link_lost", "rest"})
_NO_LIGHT = {"color": "#000000", "brightness": 0}
_INPUT = {
    "schema_version", "robot_id", "now_monotonic_ms", "source_kind",
    "voice", "display", "microphone", "gaze", "gesture",
}
_VOICE = {"phase", "observed_monotonic_ms", "capture_confirmed", "playback_confirmed"}
_DISPLAY = {"link_state", "eyes_enabled", "reduced_motion"}
_MIC = {"state", "observed_monotonic_ms"}
_GAZE = {"x", "y", "observed_monotonic_ms"}
_GESTURE = {"scene", "gesture_id", "started_monotonic_ms"}


def _object(value: Any, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Invalid {label} fields")
    return value


def _int(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError(f"Invalid {label}")
    return value


def _age(now: int, then: Any, label: str) -> int:
    timestamp = _int(then, label)
    if timestamp > now:
        raise ValueError(f"Future {label} rejected")
    return now - timestamp


def _number(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not -0.6 <= value <= 0.6:
        raise ValueError(f"Invalid {label}")
    return float(value)


def validate_input(value: Any) -> dict:
    """Parse an *offline-only* composite preview with exact typed fields."""
    p = _object(value, _INPUT, "composition input")
    if p["schema_version"] != SCHEMA or p["source_kind"] != "operator_synthetic_preview":
        raise ValueError("Only operator_synthetic_preview input is allowed")
    if not isinstance(p["robot_id"], str) or not _ROBOT.fullmatch(p["robot_id"]):
        raise ValueError("Invalid robot identifier")
    now = _int(p["now_monotonic_ms"], "monotonic time")
    display = _object(p["display"], _DISPLAY, "display")
    if display["link_state"] not in ("ready", "connecting", "lost"):
        raise ValueError("Invalid display link state")
    if type(display["eyes_enabled"]) is not bool or type(display["reduced_motion"]) is not bool:
        raise ValueError("Invalid display settings")

    voice = p["voice"]
    if voice is not None:
        _object(voice, _VOICE, "voice")
        if voice["phase"] not in PHASES:
            raise ValueError("Unknown preview phase")
        _age(now, voice["observed_monotonic_ms"], "voice sample")
        if type(voice["capture_confirmed"]) is not bool or type(voice["playback_confirmed"]) is not bool:
            raise ValueError("Invalid voice evidence flags")
    microphone = p["microphone"]
    if microphone is not None:
        _object(microphone, _MIC, "microphone")
        if microphone["state"] not in ("disabled", "monitoring", "capturing", "unknown"):
            raise ValueError("Invalid microphone state")
        _age(now, microphone["observed_monotonic_ms"], "microphone sample")
    gaze = p["gaze"]
    if gaze is not None:
        _object(gaze, _GAZE, "gaze")
        _number(gaze["x"], "gaze.x")
        _number(gaze["y"], "gaze.y")
        _age(now, gaze["observed_monotonic_ms"], "gaze sample")
    gesture = p["gesture"]
    if gesture is not None:
        _object(gesture, _GESTURE, "gesture")
        if gesture["scene"] not in SOCIAL:
            raise ValueError("Unsupported social gesture")
        identifier = gesture["gesture_id"]
        if not isinstance(identifier, str) or not _GESTURE_ID.fullmatch(identifier):
            raise ValueError("Invalid gesture id")
        _age(now, gesture["started_monotonic_ms"], "gesture start")
    return p


def compose_preview(pack: dict, input_data: dict) -> dict:
    """Plan one coherent visual scene, never schedule a timer or send I/O.

    Caller is responsible for actual event/session authentication, unique
    one-shot gesture admission, time monotonicity across calls and device
    arbitration in a separately reviewed runtime stage.
    """
    validate_pack(pack)
    inp = validate_input(input_data)
    now = inp["now_monotonic_ms"]
    voice = inp["voice"]
    mic = inp["microphone"]
    gaze = inp["gaze"]
    gesture = inp["gesture"]
    display = inp["display"]

    phase = "connecting"
    reasons = []
    voice_current = voice is not None and _age(now, voice["observed_monotonic_ms"], "voice sample") <= VOICE_STALE_MS
    if not voice_current:
        reasons.append("voice_unknown_or_stale")
    else:
        phase = voice["phase"]

    mic_state = "unknown"
    if mic is not None and _age(now, mic["observed_monotonic_ms"], "microphone sample") <= MIC_STALE_MS:
        mic_state = mic["state"]
    elif mic is not None:
        reasons.append("microphone_stale")

    if phase == "listening":
        # A Voice label alone does not verify actual microphone capture.
        if not voice["capture_confirmed"] or mic_state != "capturing":
            phase = "connecting"
            reasons.append("listening_not_confirmed")
    if phase in _PLAYBACK_STATES and not voice["playback_confirmed"]:
        phase = "connecting"
        reasons.append("playback_not_confirmed")

    if phase not in pack["scene_expressions"]:
        phase = "connecting"
        reasons.append("missing_functional_scene")
    ring_style = pack["ring_styles"].get(phase, _NO_LIGHT)
    ring = {
        "color": ring_style["color"].upper(),
        "brightness": ring_style["brightness"],
        "derived_from": phase if phase in pack["ring_styles"] else "no_style_defined",
        "applied": False,
    }
    # No ring color from a temporary gesture, even if the gesture recipe has
    # a palette. Failure of eyes alone never changes a valid ring state.
    eye_scene = phase
    if not display["eyes_enabled"]:
        eye_scene = "off"
        reasons.append("eyes_disabled")
    elif display["link_state"] == "lost":
        eye_scene = "link_lost"
        reasons.append("display_link_lost")
    elif display["link_state"] == "connecting":
        eye_scene = "connecting"
        reasons.append("display_connecting")

    if eye_scene not in pack["scene_expressions"]:
        raise ValueError("Core eye pack missing required fallback scene")
    expression_id = pack["scene_expressions"][eye_scene]
    recipe = deepcopy(pack["expressions"][expression_id])
    overlay = None
    gesture_status = "not_requested"
    if gesture is not None:
        gesture_status = "suppressed"
        social_scene = gesture["scene"]
        if social_scene not in pack["scene_expressions"]:
            raise ValueError("Core eye pack missing social scene")
        social = pack["expressions"][pack["scene_expressions"][social_scene]]
        elapsed = _age(now, gesture["started_monotonic_ms"], "gesture start")
        if elapsed >= social["duration_ms"]:
            gesture_status = "expired"
        elif (display["eyes_enabled"] and display["link_state"] == "ready"
              and eye_scene == phase and social_scene in SOCIAL_ALLOWED.get(phase, ())):
            # Social gestures change only geometry, never the functional
            # palette, Voice state, blink policy or indicator evidence.
            for side in ("left", "right"):
                for key in ("openness", "pupil_scale", "brow_tilt_deg"):
                    recipe["eyes"][side][key] = social["eyes"][side][key]
            overlay = {"scene": social_scene, "gesture_id": gesture["gesture_id"],
                       "remaining_ms": social["duration_ms"] - elapsed}
            gesture_status = "visible"

    gaze_status = "not_provided"
    if gaze is not None:
        elapsed = _age(now, gaze["observed_monotonic_ms"], "gaze sample")
        if elapsed > GAZE_STALE_MS:
            gaze_status = "expired_centered"
        elif eye_scene in ("off", "link_lost", "connecting", "error"):
            gaze_status = "suppressed_by_display_or_state"
        else:
            for side in ("left", "right"):
                recipe["eyes"][side]["gaze_x"] = gaze["x"]
                recipe["eyes"][side]["gaze_y"] = gaze["y"]
            gaze_status = "applied_in_preview"
            if recipe["animation"]["mode"] == "scan":
                recipe["animation"]["mode"] = "still"
    if gaze_status == "expired_centered":
        for side in ("left", "right"):
            recipe["eyes"][side]["gaze_x"] = 0
            recipe["eyes"][side]["gaze_y"] = 0

    if display["reduced_motion"]:
        recipe["animation"]["mode"] = "still"
        reasons.append("reduced_motion")
    validate_expression(recipe)
    return {
        "schema_version": OUTPUT_SCHEMA,
        "robot_id": inp["robot_id"],
        "source_kind": "operator_synthetic_preview",
        "voice_phase_requested": voice["phase"] if voice_current else None,
        "voice_sample_current": bool(voice_current),
        "functional_scene": phase,
        "eyes_scene": eye_scene,
        "eyes_disabled": not display["eyes_enabled"],
        "display_link_state": display["link_state"],
        "microphone_state": mic_state,
        "gesture_status": gesture_status,
        "social_overlay": overlay,
        "gaze_status": gaze_status,
        "ring_intent": ring,
        "expression": recipe,
        "eye_frame_plan": plan_eye_preview(recipe),
        "blank_pixels_intent": eye_scene == "off",
        "reasons": reasons,
        "source_authenticated": False,
        "hardware_commands_sent": False,
        "physical_output_observed": False,
        "preview_only": True,
        "non_actuating": True,
    }
