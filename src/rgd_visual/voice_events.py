"""Candidate local Voice I/O lifecycle ingress. No audio inspection or BLE access.

The caller MUST emit real lifecycle transitions and use a fresh session id when
starting a new voice producer. This volatile sequence gate is not authentication,
not a durable event log and not Chronograph/Chronon evidence.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
from typing import Protocol

SCHEMA = "openrgd.visual.voice-event.v0.1-candidate"
SOURCE = "rgd-voice"
VOICE_STATES = {
    "listening.started": "listening",
    "inference.started": "thinking",
    "playback.started": "speaking",
    "playback.ended": "idle",
    "voice.error": "error",
    "voice.ready": "idle",
}
_FIELDS = frozenset({
    "version", "command", "schema_version", "source", "session_id", "sequence", "event"
})
_SESSION = re.compile(r"^[a-fA-F0-9]{32}$")


class StateAdapter(Protocol):
    def set_state(self, name: str) -> dict: ...
    def status(self) -> dict: ...


@dataclass(frozen=True)
class VoiceEvent:
    session_id: str
    sequence: int
    name: str


def parse_voice_event(payload: object) -> VoiceEvent:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ValueError("Voice event requires exact v1 envelope fields")
    if payload.get("version") != 1 or type(payload.get("version")) is not int:
        raise ValueError("Expected IPC version=1")
    if payload.get("command") != "voice_event":
        raise ValueError("Expected command=voice_event")
    if payload.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported voice event schema")
    if payload.get("source") != SOURCE:
        raise ValueError("Unsupported voice event source")
    session = payload.get("session_id")
    if not isinstance(session, str) or not _SESSION.fullmatch(session):
        raise ValueError("Invalid voice producer session_id")
    seq = payload.get("sequence")
    if type(seq) is not int or not 0 <= seq < 2**63:
        raise ValueError("Invalid voice event sequence")
    name = payload.get("event")
    if not isinstance(name, str) or name not in VOICE_STATES:
        raise ValueError("Unknown voice lifecycle event")
    return VoiceEvent(session_id=session.lower(), sequence=seq, name=name)


class VoiceEventGate:
    """Best-effort in-process replay/ordering protection for one voice producer.

    Requests are synchronously dispatched within the single asyncio server loop.
    A restarted daemon loses the sequence window; security is handled by the
    existing same-user socket permissions, not by these sequence numbers.
    """

    def __init__(self) -> None:
        self.session_id: str | None = None
        self.last_sequence = -1
        self.last_event: str | None = None
        self._retired_sessions: deque[str] = deque(maxlen=32)

    def status(self) -> dict:
        return {
            "schema_version": SCHEMA,
            "source": SOURCE,
            "session_id": self.session_id,
            "last_sequence": self.last_sequence if self.session_id else None,
            "last_event": self.last_event,
            "physical_event_verified": False,
        }

    def consume(self, payload: object, adapter: StateAdapter) -> dict:
        voice = parse_voice_event(payload)
        if voice.session_id != self.session_id:
            if voice.session_id in self._retired_sessions:
                return self._ignored("retired_session", adapter)
            if self.session_id is not None:
                self._retired_sessions.append(self.session_id)
            self.session_id = voice.session_id
            self.last_sequence = -1
        if voice.sequence <= self.last_sequence:
            return self._ignored("duplicate_or_out_of_order", adapter)
        result = adapter.set_state(VOICE_STATES[voice.name])
        self.last_sequence = voice.sequence
        self.last_event = voice.name
        return {**result, "source_event": voice.name, "event_sequence": voice.sequence}

    @staticmethod
    def _ignored(reason: str, adapter: StateAdapter) -> dict:
        status = adapter.status()
        return {
            "accepted": False,
            "ignored": reason,
            "desired": status.get("desired"),
            "connected": status.get("connected", False),
        }
