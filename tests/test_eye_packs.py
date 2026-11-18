"""Offline regression tests for platform-owned, robot-independent eye packs."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from rgd_visual.expression_packs import load_pack, preview_profile, validate_pack
from rgd_visual.studio import preview, validate_profile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs/eyes/core-v0.1.json"


class GenericEyePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack(PACK)

    def test_pack_is_generic_and_bounded(self):
        self.assertEqual(self.pack["pack_id"], "core_eyes_v01")
        self.assertNotIn("robot_id", self.pack)
        self.assertEqual(len(self.pack["expressions"]), 21)
        self.assertEqual(len(self.pack["scene_expressions"]), 21)
        self.assertEqual(len(self.pack["voice_events"]), 6)
        self.assertEqual(len(self.pack["ring_styles"]), 6)
        self.assertTrue(all(name.startswith("core_") for name in self.pack["expressions"]))
        self.assertFalse(any("paky01" in name for name in self.pack["expressions"]))

    def test_build_profile_for_any_valid_robot(self):
        for robot in ("paky-01", "paky-02", "demo-robot", "test-rig-7"):
            p = preview_profile(self.pack, robot)
            self.assertEqual(p["robot_id"], robot)
            self.assertEqual(len(p["expressions"]), 21)
            self.assertEqual(len(p["scenes"]), 21)
            self.assertEqual(len(p["mappings"]), 27)
            self.assertTrue(p["preview_only"])
            self.assertTrue(p["non_actuating"])
            self.assertTrue(all(z["adapter_id"] is None and z["binding_status"] == "planned" for z in p["zones"]))
            self.assertIs(validate_profile(p), p)
            result = preview(p, "voice", "playback.started")
            self.assertEqual(result["scene"], "speaking")
            self.assertFalse(result["hardware_commands_sent"])
            self.assertTrue(all(o["applied"] is False for o in result["outputs"]))

    def test_no_ring_profile_and_no_mutation(self):
        before = json.dumps(self.pack, sort_keys=True)
        p = preview_profile(self.pack, "other-robot", include_ring=False)
        self.assertEqual(len(p["zones"]), 1)
        self.assertTrue(all(o["effect"] == "eye_expression" for v in p["scenes"].values() for o in v))
        p["expressions"]["core_idle"]["label"] = "changed"
        self.assertEqual(before, json.dumps(self.pack, sort_keys=True))

    def test_all_studio_routes_select_a_defined_scene(self):
        p = preview_profile(self.pack, "test-rig")
        for scene in p["scenes"]:
            result = preview(p, "studio-preview", "preview." + scene)
            self.assertEqual(result["scene"], scene)
        self.assertEqual(preview(p, "studio-preview", "preview.absent")["scene"], "connecting")
        self.assertEqual(preview(p, "voice", "voice.error")["scene"], "error")

    def test_reject_tampering_or_robot_binding(self):
        for change in (
            lambda p: p.update(robot_id="paky-01"),
            lambda p: p["expressions"]["core_idle"].update(preview_only=False),
            lambda p: p["expressions"]["core_idle"].update(expression_id="wrong"),
            lambda p: p["scene_expressions"].update(idle="unknown"),
            lambda p: p["ring_styles"]["idle"].update(brightness=True),
            lambda p: p["voice_events"].append(dict(p["voice_events"][0])),
            lambda p: p["voice_events"].append({"event":"new.event","scene":"not_there","priority":50}),
            lambda p: p["expressions"].update({"__proto__":p["expressions"]["core_idle"]}),
        ):
            with self.subTest(change=change):
                bad=deepcopy(self.pack)
                change(bad)
                with self.assertRaises(ValueError):
                    validate_pack(bad)
        for invalid in ("", "../other", "UpperCase", "__proto__", "a"*81):
            with self.subTest(robot_id=invalid):
                with self.assertRaises(ValueError):
                    preview_profile(self.pack, invalid)

    def test_pack_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema optional, dedicated CI schema job will check it")
        schema = json.loads((ROOT/"contracts/eye-pack.v0.1-candidate.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.pack)


if __name__ == "__main__":
    unittest.main()
