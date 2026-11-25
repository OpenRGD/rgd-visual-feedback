"""Session-scoped Expression Director for synthetic, offline previews only.

Owns gesture admission/lifetime and ordered snapshot consumption, not eye
geometry, Voice producer authentication, a scheduler or device delivery.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .eye_composition import PHASES, SOCIAL, compose_preview, validate_input
from .expression_packs import validate_pack

STEP_SCHEMA = "openrgd.visual.expression-director-step.v0.1-candidate"
RESULT_SCHEMA = "openrgd.visual.expression-director-result.v0.1-candidate"
MAX_GESTURE_IDS = 256
MAX_TIME = 2**63 - 1
_ID = re.compile(r"[a-f0-9]{32}")
_ROBOT = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")
_STREAMS = ("voice", "microphone", "gaze")
_STEP_FIELDS = {"schema_version", "session_id", "sequence", "composition", "gesture_request"}
_REQUEST_FIELDS = {"gesture_id", "scene", "requested_monotonic_ms"}


def _integer(value: Any, name: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_TIME:
        raise ValueError(f"Invalid {name}")
    return value


class ExpressionDirector:
    """One synthetic preview session for one robot; serialized caller only.

    No I/O, background tasks, timers, persistence or live ingress. Every step
    is a complete caller-supplied synthetic snapshot on the same simulated
    monotonic clock. Invalid frames are rejected atomically. Never restart
    an operational robot/session using this in-memory simulation.
    """

    def __init__(self, pack: dict, *, robot_id: str, session_id: str):
        if not isinstance(robot_id, str) or not _ROBOT.fullmatch(robot_id):
            raise ValueError("Invalid robot ID")
        if not isinstance(session_id, str) or not _ID.fullmatch(session_id):
            raise ValueError("Invalid synthetic session ID")
        self._pack = deepcopy(validate_pack(pack))
        if not (PHASES | SOCIAL) <= self._pack["scene_expressions"].keys():
            raise ValueError("Pack lacks required director scenes")
        self._robot_id = robot_id
        self._session_id = session_id
        self._sequence = -1
        self._now = None
        self._samples: dict[str, dict] = {}
        self._withdrawn: set[str] = set()
        self._seen: set[str] = set()
        self._active: dict | None = None

    def step(self, frame: Any) -> dict:
        """Return one director result containing the unchanged composer result.

        The entire step is validated and composed before session state commits.
        A new frame sequence cannot renew an old source sample or gesture.
        """
        if not isinstance(frame, dict) or set(frame) != _STEP_FIELDS:
            raise ValueError("Expected exact synthetic director step fields")
        if frame["schema_version"] != STEP_SCHEMA or frame["session_id"] != self._session_id:
            raise ValueError("Unsupported schema or wrong preview session")
        seq = _integer(frame["sequence"], "sequence")
        if seq <= self._sequence:
            raise ValueError("Duplicate or out-of-order frame")

        base = deepcopy(frame["composition"])
        if not isinstance(base, dict) or base.get("gesture", False) is not None:
            raise ValueError("Director exclusively owns the composition gesture")
        try:
            validate_input(base)
        except TypeError as exc:
            raise ValueError("Invalid composition field type") from exc
        if base["robot_id"] != self._robot_id:
            raise ValueError("Wrong preview robot")
        now = base["now_monotonic_ms"]
        if self._now is not None and now < self._now:
            raise ValueError("Monotonic preview clock regressed")

        request = deepcopy(frame["gesture_request"])
        requested = None
        if request is not None:
            if not isinstance(request, dict) or set(request) != _REQUEST_FIELDS:
                raise ValueError("Invalid gesture request fields")
            requested = _integer(request["requested_monotonic_ms"], "request time")
            candidate = {"scene": request["scene"], "gesture_id": request["gesture_id"],
                         "started_monotonic_ms": requested}
            try:
                validate_input({**base, "gesture": candidate})
            except TypeError as exc:
                raise ValueError("Invalid gesture field type") from exc

        # Stage copies: validation or composition failures must not burn IDs
        # or advance the clock/sequence, even when a candidate was supplied.
        samples = deepcopy(self._samples)
        withdrawn = set(self._withdrawn)
        seen = set(self._seen)
        active = deepcopy(self._active)
        for name in _STREAMS:
            current = base[name]
            previous = samples.get(name)
            if current is None:
                if previous is not None:
                    withdrawn.add(name)
                continue
            if previous is not None:
                t = current["observed_monotonic_ms"]
                old_t = previous["observed_monotonic_ms"]
                if t < old_t:
                    raise ValueError(f"{name} sample regressed")
                if t == old_t:
                    if current != previous:
                        raise ValueError(f"{name} sample conflicts at same timestamp")
                    if name in withdrawn:
                        raise ValueError(f"{name} sample was withdrawn")
                    # Exact repeats are permitted, but retain original timestamp.
                    continue
            samples[name] = deepcopy(current)
            withdrawn.discard(name)

        transition = "none"
        ended_id = None
        base_result = compose_preview(self._pack, base)
        result = base_result
        if active is not None:
            result = compose_preview(self._pack, {**base, "gesture": active})
            if result["gesture_status"] != "visible":
                transition = ("expired" if result["gesture_status"] == "expired"
                              else "interrupted")
                ended_id = active["gesture_id"]
                active = None
                result = base_result

        decision = "not_requested"
        if request is not None:
            gid = request["gesture_id"]
            if gid in seen:
                decision = "duplicate_ignored"
            elif len(seen) >= MAX_GESTURE_IDS:
                # Do not evict any old ID and accidentally permit replay.
                decision = "session_capacity_reached"
            else:
                seen.add(gid)
                if self._now is not None and requested < self._now:
                    decision = "late_request"
                else:
                    proposed = compose_preview(self._pack, {**base, "gesture": candidate})
                    if proposed["gesture_status"] == "expired":
                        decision = "expired_request"
                    elif proposed["gesture_status"] != "visible":
                        decision = "incompatible"
                    else:
                        decision = "admitted"
                        if active is not None:
                            ended_id = active["gesture_id"]
                            transition = "replaced"
                        active = candidate
                        result = proposed

        self._samples = samples
        self._withdrawn = withdrawn
        self._seen = seen
        self._active = active
        self._sequence = seq
        self._now = now
        return {
            "schema_version": RESULT_SCHEMA,
            "robot_id": self._robot_id,
            "session_id": self._session_id,
            "sequence": seq,
            "now_monotonic_ms": now,
            "source_kind": "operator_synthetic_preview",
            "gesture_decision": decision,
            "previous_gesture_transition": transition,
            "ended_gesture_id": ended_id,
            "active_gesture_id": active["gesture_id"] if active else None,
            "seen_gesture_count": len(seen),
            "composition": result,
            "source_authenticated": False,
            "hardware_commands_sent": False,
            "physical_output_observed": False,
            "actuation_enabled": False,
            "preview_only": True,
            "non_actuating": True,
        }
