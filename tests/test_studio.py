"""Offline contract/engine checks. No robot, Bluetooth, network or device access."""
import copy
from pathlib import Path
import unittest

from rgd_visual.studio import SCHEMA, load_profile, preview, validate_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/paky01-studio.preview.json"


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(PROFILE)

    def test_voice_events_resolve_consistently(self):
        expected = [
            ("listening.started", "listening", "#0050FF"),
            ("inference.started", "thinking", "#9600FF"),
            ("playback.started", "speaking", "#00FF46"),
            ("playback.ended", "idle", "#FFFFFF"),
            ("voice.error", "error", "#FF0000"),
        ]
        for event, scene, color in expected:
            with self.subTest(event=event):
                result = preview(self.profile, "voice", event)
                self.assertEqual(result["scene"], scene)
                self.assertEqual(result["outputs"][0]["color"], color)
                self.assertTrue(result["matched"])
                self.assertFalse(result["hardware_commands_sent"])
                self.assertFalse(result["outputs"][0]["applied"])
                self.assertFalse(result["outputs"][0]["physical_light_observed"])

    def test_unrecognized_event_falls_back_safely(self):
        value = preview(self.profile, "vision", "face.detected")
        self.assertFalse(value["matched"])
        self.assertEqual(value["scene"], "idle")
        self.assertTrue(value["preview_only"])

    def test_new_zones_support_future_effects_without_claiming_hardware(self):
        result = preview(self.profile, "system", "operator.welcome")
        self.assertEqual(result["scene"], "welcome")
        self.assertEqual(len(result["outputs"]), 2)
        planned = next(x for x in result["outputs"] if x["zone_id"] == "room-lights")
        self.assertEqual(planned["effect"], "pulse")
        self.assertFalse(planned["eligible_by_declared_capabilities"])
        self.assertEqual(planned["reason"], "planned_zone")

    def test_priority_is_deterministic_and_refuses_duplicate_equal_priority(self):
        p = copy.deepcopy(self.profile)
        p["mappings"].append({"source": "voice", "event": "playback.started",
                              "scene": "error", "priority": 90})
        self.assertEqual(preview(p, "voice", "playback.started")["scene"], "error")
        p["mappings"].append({"source": "voice", "event": "playback.started",
                              "scene": "idle", "priority": 90})
        with self.assertRaisesRegex(ValueError, "Ambiguous mapping"):
            validate_profile(p)

    def test_unsafe_profile_or_unknown_zone_rejected(self):
        candidates = []
        p = copy.deepcopy(self.profile)
        p["preview_only"] = False
        candidates.append(p)
        p = copy.deepcopy(self.profile)
        p["non_actuating"] = False
        candidates.append(p)
        p = copy.deepcopy(self.profile)
        p["scenes"]["idle"][0]["zone_id"] = "not-a-zone"
        candidates.append(p)
        p = copy.deepcopy(self.profile)
        p["scenes"]["idle"][0]["brightness"] = 101
        candidates.append(p)
        p = copy.deepcopy(self.profile)
        p["scenes"]["idle"][0]["brightness"] = True
        candidates.append(p)
        p = copy.deepcopy(self.profile)
        p["scenes"]["idle"][0]["effect"] = "exec"
        candidates.append(p)
        p = copy.deepcopy(self.profile)
        p["unknown"] = "injection"
        candidates.append(p)
        for candidate in candidates:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                validate_profile(candidate)

    def test_schema_and_identity_immutable_in_preview(self):
        self.assertEqual(self.profile["schema_version"], SCHEMA)
        result = preview(self.profile, "voice", "playback.started")
        self.assertEqual(result["robot_id"], "paky-01")
        self.assertTrue(result["non_actuating"])


if __name__ == "__main__":
    unittest.main()
