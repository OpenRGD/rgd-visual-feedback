"""Candidate Cognitive → Visual expression proof, *offline only*.

No TTS/cognition provider, BLE, display driver or network service is used.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from rgd_visual.expressions import (
    EXPRESSION_SCHEMA, PROPOSAL_SCHEMA, plan_cognitive_proposal,
    plan_eye_preview, read_preview, validate_expression, validate_proposal,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/expressions/meraviglia_curiosa.preview.json"
PROPOSAL = ROOT / "examples/expressions/cognitive-meraviglia.proposal.json"


class VisualExpressionTests(unittest.TestCase):
    def setUp(self):
        self.expr = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))

    def test_new_expression_name_is_not_an_enum(self):
        for new_name in ("meraviglia_curiosa", "curiosita_affettuosa", "stupore_silenzioso"):
            with self.subTest(expression_id=new_name):
                expr = deepcopy(self.expr)
                expr["expression_id"] = new_name
                accepted = validate_expression(expr)
                self.assertEqual(accepted["expression_id"], new_name)
                self.assertEqual(accepted["schema_version"], EXPRESSION_SCHEMA)

    def test_eye_frame_plan_keeps_each_eye_independent(self):
        plan = plan_eye_preview(self.expr)
        self.assertEqual(plan["expression_id"], "meraviglia_curiosa")
        self.assertNotEqual(
            plan["eye_frames"]["left"]["brow_tilt_deg"],
            plan["eye_frames"]["right"]["brow_tilt_deg"],
        )
        self.assertFalse(plan["hardware_commands_sent"])
        self.assertFalse(plan["physical_output_observed"])
        self.assertFalse(plan["emotion_internal_state_verified"])
        self.assertFalse(plan["accent_ring_intent"]["applied"])
        self.assertEqual(plan["animation"]["blink_interval_ms"], 5200)

    def test_cognitive_proposal_previews_without_registering(self):
        self.assertEqual(self.proposal["contract"], PROPOSAL_SCHEMA)
        plan = plan_cognitive_proposal(self.proposal)
        self.assertEqual(plan["robot_id"], "paky-02")
        self.assertTrue(plan["approval_required_for_persistence"])
        self.assertFalse(plan["persistence_performed"])
        self.assertEqual(plan["operator_review_status"], "pending")
        self.assertTrue(plan["preview_only"])

    def test_untrusted_recipe_must_not_execute_or_claim_emotion(self):
        rejected = []
        for key, value in (
            ("preview_only", False),
            ("non_actuating", False),
            ("claims_emotion_as_internal_state", True),
            ("origin", "system_admin"),
            ("expression_id", "__import__('os').system"),
            ("label", "Hello\ninjected"),
            ("shader", "eval(1+1)"),
        ):
            bad = deepcopy(self.expr)
            bad[key] = value
            rejected.append(bad)
        bad = deepcopy(self.expr)
        bad["eyes"]["left"]["pupil_scale"] = 100
        rejected.append(bad)
        bad = deepcopy(self.expr)
        bad["eyes"]["right"]["gaze_y"] = float("nan")
        rejected.append(bad)
        bad = deepcopy(self.expr)
        bad["palette"]["ring_brightness_pct"] = 80
        rejected.append(bad)
        bad = deepcopy(self.expr)
        bad["palette"]["ring_brightness_pct"] = True
        rejected.append(bad)
        bad = deepcopy(self.expr)
        bad["animation"]["blink_interval_ms"] = 30
        rejected.append(bad)
        bad = deepcopy(self.expr)
        bad["animation"]["mode"] = "execute_script"
        rejected.append(bad)
        bad = deepcopy(self.expr)
        bad["duration_ms"] = 999999
        rejected.append(bad)
        for candidate in rejected:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                validate_expression(candidate)

    def test_cognitive_may_not_authorize_persistence_or_hardware(self):
        rejected = []
        for key, value in [
            ("source_module", "org.openrgd.admin"),
            ("source_sequence", -1),
            ("source_sequence", True),
            ("source_session_id", "invalid"),
            ("requested_at_utc", "2026-10-26T12:00:00"),
            ("presentation", "apply_now"),
            ("approval_required_for_persistence", False),
            ("hardware_execution_authorized", True),
            ("command", "flash_software"),
        ]:
            bad = deepcopy(self.proposal)
            bad[key] = value
            rejected.append(bad)
        bad = deepcopy(self.proposal)
        bad["expression"]["origin"] = "operator"
        rejected.append(bad)
        for proposal in rejected:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                validate_proposal(proposal)

    def test_bounded_input_rejects_huge_and_symlinked_json(self):
        self.assertEqual(read_preview(FIXTURE)["expression_id"], "meraviglia_curiosa")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            huge = root / "huge.json"
            huge.write_text(" " * (17 * 1024), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_preview(huge)
            link = root / "linked.json"
            link.symlink_to(FIXTURE)
            with self.assertRaises(ValueError):
                read_preview(link)


if __name__ == "__main__":
    unittest.main()
