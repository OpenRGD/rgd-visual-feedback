"""Pure offline tests: no BLE device, event bus or robot required."""
import unittest
from rgd_visual.voice_events import SCHEMA, VoiceEventGate, VOICE_STATES, parse_voice_event


class FakeAdapter:
    def __init__(self):
        self.desired = "idle"
        self.calls = []

    def set_state(self, name):
        self.calls.append(name)
        self.desired = name
        return {"accepted": True, "desired": name, "connected": False}

    def status(self):
        return {"desired": self.desired, "connected": False}


def envelope(name, sequence=0, session="a" * 32):
    return {
        "version": 1, "command": "voice_event", "schema_version": SCHEMA,
        "source": "rgd-voice", "session_id": session,
        "sequence": sequence, "event": name,
    }


class VoiceEventTests(unittest.TestCase):
    def test_state_mapping_is_complete_and_explicit(self):
        gate = VoiceEventGate()
        adapter = FakeAdapter()
        expected = [
            ("listening.started", "listening"),
            ("inference.started", "thinking"),
            ("playback.started", "speaking"),
            ("playback.ended", "idle"),
            ("voice.error", "error"),
            ("voice.ready", "idle"),
        ]
        for seq, (event, state) in enumerate(expected):
            result = gate.consume(envelope(event, seq), adapter)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["desired"], state)
        self.assertEqual(adapter.calls, [state for _, state in expected])
        self.assertEqual(len(VOICE_STATES), len(expected))
        self.assertFalse(gate.status()["physical_event_verified"])

    def test_duplicate_or_out_of_order_event_does_not_change_state(self):
        gate = VoiceEventGate()
        adapter = FakeAdapter()
        gate.consume(envelope("playback.started", 8), adapter)
        for seq in (8, 7):
            result = gate.consume(envelope("playback.ended", seq), adapter)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["ignored"], "duplicate_or_out_of_order")
        self.assertEqual(adapter.calls, ["speaking"])

    def test_old_session_cannot_override_new_session(self):
        gate = VoiceEventGate()
        adapter = FakeAdapter()
        gate.consume(envelope("listening.started", 4, "a" * 32), adapter)
        gate.consume(envelope("playback.started", 0, "b" * 32), adapter)
        result = gate.consume(envelope("playback.ended", 5, "a" * 32), adapter)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["ignored"], "retired_session")
        self.assertEqual(adapter.desired, "speaking")

    def test_bad_envelopes_are_rejected_before_state_change(self):
        original = envelope("listening.started")
        bad = [
            {**original, "version": True},
            {**original, "sequence": True},
            {**original, "sequence": -1},
            {**original, "sequence": 2**63},
            {**original, "session_id": "../../../etc/passwd"},
            {**original, "source": "another-client"},
            {**original, "event": "tts.requested"},
            {**original, "schema_version": "made-up"},
            {**original, "debug": "extra"},
        ]
        gate = VoiceEventGate()
        adapter = FakeAdapter()
        for payload in bad:
            with self.assertRaises(ValueError):
                parse_voice_event(payload)
            with self.assertRaises(ValueError):
                gate.consume(payload, adapter)
        self.assertEqual(adapter.calls, [])


if __name__ == "__main__":
    unittest.main()
