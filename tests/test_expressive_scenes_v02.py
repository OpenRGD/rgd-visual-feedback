"""VISUAL-0.2B: additive expression scenes, strict backwards compatibility.

Pure offline preview. No BLE, Python eval, screen framebuffer or host I/O.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from rgd_visual.studio import SCHEMA, SCHEMA_V02, preview, stage_expression_preview, validate_profile

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "profiles/paky01-studio.preview.json"
NEW = ROOT / "profiles/paky02-expressive-studio.preview.json"


class ExpressiveSceneV02Tests(unittest.TestCase):
    def setUp(self):
        self.old = json.loads(OLD.read_text(encoding="utf-8"))
        self.new = json.loads(NEW.read_text(encoding="utf-8"))

    def test_v01_legacy_profile_and_outputs_remain_unchanged(self):
        self.assertEqual(self.old["schema_version"], SCHEMA)
        self.assertIs(validate_profile(self.old), self.old)
        result = preview(self.old, "voice", "playback.started")
        self.assertEqual(result["scene"], "speaking")
        self.assertEqual(len(result["outputs"]), 1)
        light = result["outputs"][0]
        self.assertEqual(light["effect"], "solid")
        self.assertEqual(light["color"], "#00FF46")
        self.assertEqual(light["brightness"], 35)
        self.assertNotIn("frame_plan", light)
        self.assertNotIn("expression_id", light)
        self.assertFalse(light["applied"])
        self.assertFalse(result["hardware_commands_sent"])

    def test_v02_scene_can_combine_led_room_and_eyes(self):
        self.assertEqual(self.new["schema_version"], SCHEMA_V02)
        validate_profile(self.new)
        result = preview(self.new, "system", "operator.welcome")
        self.assertEqual(result["scene"], "welcome")
        self.assertEqual(len(result["outputs"]), 3)
        eyes = next(x for x in result["outputs"] if x["effect"] == "eye_expression")
        self.assertEqual(eyes["zone_id"], "expressive-eyes")
        self.assertEqual(eyes["expression_id"], "meraviglia_curiosa")
        self.assertEqual(eyes["frame_plan"]["expression_id"], "meraviglia_curiosa")
        self.assertNotEqual(
            eyes["frame_plan"]["eye_frames"]["left"]["brow_tilt_deg"],
            eyes["frame_plan"]["eye_frames"]["right"]["brow_tilt_deg"]
        )
        self.assertFalse(eyes["frame_plan"]["hardware_commands_sent"])
        self.assertFalse(eyes["physical_light_observed"])
        self.assertFalse(eyes["eligible_by_declared_capabilities"])
        self.assertEqual(eyes["reason"], "planned_zone")
        self.assertEqual(
            {(v["zone_id"], v["effect"]) for v in result["outputs"]},
            {("face-ring", "solid"), ("room-lights", "pulse"), ("expressive-eyes", "eye_expression")},
        )

    def test_v02_can_add_new_expression_without_engine_change(self):
        p = deepcopy(self.new)
        invented = deepcopy(p["expressions"]["meraviglia_curiosa"])
        invented["expression_id"] = "attenzione_gentile"
        invented["label"] = "Attenzione gentile"
        invented["eyes"]["left"]["openness"] = 0.62
        p["expressions"]["attenzione_gentile"] = invented
        p["scenes"]["eyes_only"][0]["expression_id"] = "attenzione_gentile"
        out = preview(p, "studio", "preview.meraviglia_curiosa")
        eye = out["outputs"][0]
        self.assertEqual(eye["expression_id"], "attenzione_gentile")
        self.assertEqual(eye["frame_plan"]["eye_frames"]["left"]["openness"], 0.62)
        self.assertTrue(out["preview_only"])
        self.assertFalse(out["hardware_commands_sent"])

    def test_rejects_malformed_or_nonexistent_expression(self):
        invalids = []
        p = deepcopy(self.new)
        p["expressions"]["meraviglia_curiosa"]["expression_id"] = "wrong_id"
        invalids.append(p)
        p = deepcopy(self.new)
        p["scenes"]["welcome"][-1]["expression_id"] = "missing_expression"
        invalids.append(p)
        p = deepcopy(self.new)
        p["scenes"]["welcome"][-1]["script"] = "eval('malicious')"
        invalids.append(p)
        p = deepcopy(self.new)
        p["scenes"]["welcome"][-1]["color"] = "#FFFFFF"
        invalids.append(p)
        p = deepcopy(self.new)
        p["scenes"]["eyes_only"][-1]["effect"] = "system.exec"
        invalids.append(p)
        p = deepcopy(self.new)
        p["expressions"]["meraviglia_curiosa"]["non_actuating"] = False
        invalids.append(p)
        p = deepcopy(self.new)
        p["expressions"]["meraviglia_curiosa"]["palette"]["ring_brightness_pct"] = 100
        invalids.append(p)
        p = deepcopy(self.new)
        p["expressions"] = {f"test_emotion_{n:02d}": {**deepcopy(p["expressions"]["meraviglia_curiosa"]), "expression_id": f"test_emotion_{n:02d}"} for n in range(33)}
        invalids.append(p)
        for invalid in invalids:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_profile(invalid)

    def test_v01_cannot_silently_accept_v02_features(self):
        invalids = []
        p = deepcopy(self.old)
        p["expressions"] = {}
        invalids.append(p)
        p = deepcopy(self.old)
        p["zones"][0]["capabilities"].append("eye_expression")
        invalids.append(p)
        p = deepcopy(self.old)
        p["scenes"]["idle"][0] = {"zone_id": "face-ring", "effect": "eye_expression", "expression_id": "fake"}
        invalids.append(p)
        for invalid in invalids:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_profile(invalid)

    def test_cognitive_proposal_stages_new_expression_without_mutation(self):
        p = deepcopy(self.new)
        proposal = json.loads((ROOT / "examples/expressions/cognitive-meraviglia.proposal.json")
                              .read_text(encoding="utf-8"))
        invented = deepcopy(proposal["expression"])
        invented["expression_id"] = "gioia_riflessiva"
        invented["label"] = "Gioia riflessiva"
        invented["eyes"]["right"]["openness"] = 0.49
        proposal["expression"] = invented
        result = stage_expression_preview(p, proposal, "welcome")
        self.assertEqual(result["expression_id"], "gioia_riflessiva")
        self.assertTrue(result["catalog_changed"])
        self.assertTrue(result["preview_only"])
        self.assertEqual(result["operator_review_status"], "pending")
        self.assertFalse(result["persistence_performed"])
        self.assertFalse(result["hardware_commands_sent"])
        self.assertFalse(result["physical_output_observed"])
        self.assertNotIn("gioia_riflessiva", p["expressions"])
        self.assertIn("gioia_riflessiva", result["profile_candidate"]["expressions"])
        outcome = preview(result["profile_candidate"], "system", "operator.welcome")
        staged = next(x for x in outcome["outputs"] if x["effect"] == "eye_expression")
        self.assertEqual(staged["expression_id"], "gioia_riflessiva")
        self.assertEqual(staged["frame_plan"]["eye_frames"]["right"]["openness"], 0.49)

    def test_cross_robot_cognitive_and_unwrapped_proposals_rejected(self):
        proposal = json.loads((ROOT / "examples/expressions/cognitive-meraviglia.proposal.json")
                              .read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "robot id"):
            stage_expression_preview({**self.new, "robot_id": "paky-01"}, proposal, "welcome")
        with self.assertRaisesRegex(ValueError, "full validated proposal"):
            stage_expression_preview(self.new, proposal["expression"], "welcome")

    def test_operator_recipes_allowed_but_never_auto_persisted(self):
        recipe = deepcopy(self.new["expressions"]["meraviglia_curiosa"])
        recipe["origin"] = "operator"
        recipe["expression_id"] = "calma_attenta"
        staged = stage_expression_preview(self.new, recipe, "eyes_only")
        self.assertEqual(staged["source_kind"], "operator")
        self.assertFalse(staged["persistence_performed"])
        self.assertNotIn(recipe["expression_id"], self.new["expressions"])

    def test_catalog_replacement_requires_explicit_preview_flag(self):
        recipe = deepcopy(self.new["expressions"]["meraviglia_curiosa"])
        recipe["origin"] = "operator"
        with self.assertRaisesRegex(ValueError, "explicit replacement"):
            stage_expression_preview(self.new, recipe, "welcome")
        staged = stage_expression_preview(self.new, recipe, "welcome", replace_existing=True)
        self.assertEqual(staged["profile_candidate"]["expressions"][recipe["expression_id"]]["origin"], "operator")
        self.assertEqual(self.new["expressions"][recipe["expression_id"]]["origin"], "cognitive_proposal")

    def test_wrong_capability_and_legacy_staging_rejected(self):
        p = deepcopy(self.new)
        p["zones"][-1]["capabilities"] = ["solid"]
        with self.assertRaisesRegex(ValueError, "capability"):
            stage_expression_preview(p, self.new["expressions"]["meraviglia_curiosa"], "welcome")
        with self.assertRaisesRegex(ValueError, "v0.2"):
            stage_expression_preview(self.old, self.new["expressions"]["meraviglia_curiosa"], "welcome")

    def test_v02_undefined_zone_capability_remains_non_eligible(self):
        p = deepcopy(self.new)
        p["zones"][-1]["capabilities"] = ["solid"]
        result = preview(p, "studio", "preview.meraviglia_curiosa")
        eye = result["outputs"][0]
        self.assertEqual(eye["reason"], "effect_not_supported_by_declared_zone")
        self.assertFalse(eye["eligible_by_declared_capabilities"])


if __name__ == "__main__":
    unittest.main()
