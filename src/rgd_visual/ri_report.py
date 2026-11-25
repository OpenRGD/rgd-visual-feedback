"""VISUAL-RI-01: inert report projection, NOT a sensor, event bus or driver.

The caller supplies an existing status snapshot. No socket, BLE, RI runtime,
clock sampling, evidence store, gaze policy or output operation is invoked.
The source's actual event time and cue identity are unavailable in legacy IPC.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from .config import REQUIRED_STATES
from .voice_events import SCHEMA as VOICE_SCHEMA, SOURCE as VOICE_SOURCE, VOICE_STATES

SCHEMA = "openrgd.visual.ri-status-report.v0.1-candidate"
INPUT_KINDS = ("unverified_snapshot", "synthetic", "replay")
MAX_INPUT_BYTES = 16 * 1024
_STATUS = {"ok", "adapter", "address", "connected", "desired", "applied", "last_error"}
_VOICE_STATUS = {"schema_version", "source", "session_id", "last_sequence",
                 "last_event", "physical_event_verified"}
_MAC = re.compile(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}")
_SESSION = re.compile(r"[0-9a-f]{32}")


def _report(kind: str, owner: str, proof: str, fields: dict) -> dict:
    return {
        "event_kind": kind,
        "source_owner": owner,
        "reported_by": "rgd-visual-feedback",
        "occurred_at": None,
        "clock_domain_id": None,
        "proof": proof,
        "data": fields,
    }


def _voice_report(voice: Any) -> dict | None:
    if not isinstance(voice, dict) or set(voice) != _VOICE_STATUS:
        raise ValueError("Invalid legacy Voice status")
    if (voice["schema_version"] != VOICE_SCHEMA or voice["source"] != VOICE_SOURCE
            or voice["physical_event_verified"] is not False):
        raise ValueError("Unsupported Voice status or physical claim")
    session, seq, event = (voice[k] for k in ("session_id", "last_sequence", "last_event"))
    if session is None and seq is None and event is None:
        return None
    if (not isinstance(session, str) or not _SESSION.fullmatch(session)
            or type(seq) is not int or not 0 <= seq < 2**63
            or not isinstance(event, str) or event not in VOICE_STATES):
        raise ValueError("Inconsistent legacy Voice status")
    return _report(
        "voice.lifecycle.last_accepted_report", "rgd-voice", "visual_gate_status_only",
        {"source_schema": VOICE_SCHEMA, "session_id": session,
         "sequence": seq, "event": event},
    )


def project_status(snapshot: Any, *, input_kind: str) -> dict:
    """Project a copy of a legacy status snapshot; never accept a command.

    Input classification is caller-declared and unverified. Even a reported
    successful BLE write is only a snapshot of the last applied state, not a
    new acknowledgement tied to a cue, nor a physical observation.
    """
    if input_kind not in INPUT_KINDS:
        raise ValueError("Explicit unverified_snapshot/synthetic/replay required")
    if not isinstance(snapshot, dict) or set(snapshot) not in (_STATUS, _STATUS | {"voice_event"}):
        raise ValueError("Expected exact legacy status fields")
    if snapshot["ok"] is not True or snapshot["adapter"] != "miracles-star-ble":
        raise ValueError("Status unavailable or unsupported adapter")
    if not isinstance(snapshot["address"], str) or not _MAC.fullmatch(snapshot["address"]):
        raise ValueError("Invalid legacy adapter address")
    connected, desired, applied, error = (
        snapshot[k] for k in ("connected", "desired", "applied", "last_error"))
    if type(connected) is not bool or desired not in REQUIRED_STATES:
        raise ValueError("Invalid driver status")
    if applied is not None and (applied not in REQUIRED_STATES or not connected):
        raise ValueError("Inconsistent last applied state")
    if error is not None and (not isinstance(error, str) or len(error) > 300):
        raise ValueError("Invalid legacy error field")
    reports = [_report(
        "visual.delivery.status_snapshot", "rgd-visual-feedback", "driver_status_only",
        {"adapter": "miracles-star-ble", "connected": connected,
         "desired": desired, "rendered_scene": None, "applied": applied,
         "driver_ack_reported": applied is not None, "error_reported": error is not None},
    )]
    if "voice_event" in snapshot:
        voice = _voice_report(snapshot["voice_event"])
        if voice is not None:
            reports.append(voice)
    return {
        "schema_version": SCHEMA,
        "input_kind": input_kind,
        "freshness": "unknown",
        "source_authenticated": False,
        "robot_binding_verified": False,
        "physical_output_observed": False,
        "physical_observation_ref": None,
        "history_committed": False,
        "actuation_enabled": False,
        "may_drive_visual": False,
        "non_actuating": True,
        "reports": reports,
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate JSON key")
        out[key] = value
    return out


def decode_snapshot(raw: bytes) -> dict:
    if not 0 < len(raw) <= MAX_INPUT_BYTES:
        raise ValueError("Empty or oversized status snapshot")
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Project a supplied Visual status snapshot (offline only)")
    parser.add_argument("--input-kind", choices=INPUT_KINDS, required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        result = project_status(decode_snapshot(raw), input_kind=args.input_kind)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        # Never echo raw device addresses, error strings or malformed inputs.
        print("Invalid or unavailable status snapshot; no report emitted", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
