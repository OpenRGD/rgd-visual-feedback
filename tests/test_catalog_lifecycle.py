"""VISUAL-0.2C — durable catalog regression tests, isolated temp directories.

Zero audio, Bluetooth, mini display, Somatic Runtime or cloud access.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from rgd_visual.catalog import CatalogStore, _digest

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = json.loads((ROOT / "examples/expressions/cognitive-curiosita-gentile.proposal.json")
                      .read_text(encoding="utf-8"))
OPERATOR = json.loads((ROOT / "examples/expressions/meraviglia_curiosa.preview.json")
                      .read_text(encoding="utf-8"))
OPERATOR["origin"] = "operator"


class ExpressionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rgd-catalog-offline-")
        self.path = Path(self.tmp.name) / "catalog"
        self.store = CatalogStore(self.path, "paky-02")

    def tearDown(self):
        self.tmp.cleanup()

    def queue_cognitive(self, candidate=None):
        return self.store.queue(deepcopy(candidate or PROPOSAL))

    def approve(self, proposal_id, expected=0):
        return self.store.approve(
            proposal_id, expected_revision=expected,
            confirmation=f"APPROVE paky-02 {proposal_id}"
        )

    def test_queries_do_not_create_storage_or_connect_to_device(self):
        self.assertFalse(self.path.exists())
        self.assertEqual(self.store.list_catalog(), [])
        self.assertEqual(self.store.list_proposals(), [])
        self.assertEqual(self.store.history("curiosita_gentile"), [])
        self.assertFalse(self.path.exists())

    def test_queue_is_pending_not_hardware_approval(self):
        response = self.queue_cognitive()
        self.assertTrue(response["persistence_performed"])
        self.assertEqual(response["status"], "pending")
        self.assertFalse(response["hardware_execution_authorized"])
        self.assertFalse(response["hardware_commands_sent"])
        self.assertEqual(self.store.list_catalog(), [])
        statuses = self.store.list_proposals()
        self.assertEqual(statuses[0]["status"], "pending")
        self.assertEqual(statuses[0]["expression_id"], "curiosita_gentile")
        for directory in [self.path, self.store.robot_dir, self.store.proposals_dir]:
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        for file in self.store.proposals_dir.glob("*.json"):
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)

    def test_explicit_approval_creates_revision_and_survives_new_instance(self):
        proposal_id = self.queue_cognitive()["proposal_id"]
        with self.assertRaises(PermissionError):
            self.store.approve(proposal_id, expected_revision=0, confirmation="yes")
        self.assertEqual(self.store.list_catalog(), [])
        receipt = self.approve(proposal_id)
        self.assertEqual(receipt["revision"], 1)
        self.assertTrue(receipt["catalog_revision_saved"])
        self.assertFalse(receipt["scene_profile_modified"])
        self.assertFalse(receipt["hardware_commands_sent"])
        other_process = CatalogStore(self.path, "paky-02")
        self.assertEqual(other_process.show("curiosita_gentile")["revision"], 1)
        self.assertEqual(other_process.list_catalog()[0]["label"], "Curiosità gentile")
        self.assertEqual(other_process.list_proposals()[0]["status"], "approved")
        self.assertEqual(stat.S_IMODE(other_process._revision_dir("curiosita_gentile").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((other_process._revision_dir("curiosita_gentile") / "rev-000001.json").stat().st_mode), 0o600)

    def test_two_approved_versions_and_rollback_append_new_revision(self):
        first = self.queue_cognitive()["proposal_id"]
        self.approve(first, expected=0)
        expression = deepcopy(OPERATOR)
        expression["expression_id"] = "curiosita_gentile"
        expression["label"] = "Curiosità gentile rielaborata"
        expression["eyes"]["right"]["openness"] = 0.36
        second = self.store.queue(expression)["proposal_id"]
        self.approve(second, expected=1)
        before = self.store.history("curiosita_gentile")
        self.assertEqual([r["revision"] for r in before], [1, 2])
        with self.assertRaises(PermissionError):
            self.store.rollback("curiosita_gentile", to_revision=1,
                                expected_revision=2, confirmation="ROLLBACK")
        rollback = self.store.rollback("curiosita_gentile", to_revision=1,
                        expected_revision=2,
                        confirmation="ROLLBACK paky-02 curiosita_gentile TO 1")
        self.assertEqual(rollback["revision"], 3)
        self.assertEqual(self.store.show("curiosita_gentile")["expression"], before[0]["expression"])
        self.assertEqual(self.store.history("curiosita_gentile")[-1]["rollback_source_revision"], 1)
        self.assertEqual(self.store.list_catalog()[0]["last_action"], "rollback")
        self.assertEqual(len(self.store.history("curiosita_gentile")), 3)
        self.assertFalse(rollback["hardware_execution_authorized"])

    def test_compare_and_swap_revision_and_replays_are_rejected(self):
        proposal_id = self.queue_cognitive()["proposal_id"]
        with self.assertRaisesRegex(ValueError, "replayed"):
            self.queue_cognitive()
        with self.assertRaisesRegex(ValueError, "Stale expected revision"):
            self.approve(proposal_id, expected=2)
        self.approve(proposal_id, expected=0)
        with self.assertRaisesRegex(ValueError, "already approved"):
            self.approve(proposal_id, expected=1)
        self.assertEqual(len(self.store.history("curiosita_gentile")), 1)

    def test_cross_robot_proposal_does_not_enter_foreign_catalog(self):
        with self.assertRaisesRegex(ValueError, "robot mismatch"):
            CatalogStore(self.path, "paky-01").queue(deepcopy(PROPOSAL))
        self.assertFalse((self.path / "paky-01").exists())
        self.queue_cognitive()
        self.assertEqual(CatalogStore(self.path, "paky-01").list_catalog(), [])
        self.assertEqual(CatalogStore(self.path, "paky-01").list_proposals(), [])

    def test_bare_cognitive_recipe_cannot_bypass_wrapper(self):
        with self.assertRaisesRegex(ValueError, "Unwrapped Cognitive"):
            self.store.queue(deepcopy(PROPOSAL["expression"]))
        self.assertFalse(self.path.exists())

    def test_operator_recipe_needs_same_review_and_approval(self):
        queued = self.store.queue(deepcopy(OPERATOR))
        self.assertNotEqual(queued["proposal_id"], PROPOSAL["proposal_id"])
        self.assertEqual(self.store.list_catalog(), [])
        with self.assertRaises(PermissionError):
            self.store.approve(queued["proposal_id"], expected_revision=0, confirmation="approve")
        approved = self.approve(queued["proposal_id"])
        self.assertEqual(approved["revision"], 1)
        self.assertEqual(self.store.show(OPERATOR["expression_id"])["expression"]["origin"], "operator")

    def test_reject_keeps_proposal_for_audit_and_blocks_approval(self):
        proposal_id = self.queue_cognitive()["proposal_id"]
        with self.assertRaises(PermissionError):
            self.store.reject(proposal_id, reason="not reviewed", confirmation="reject")
        result = self.store.reject(proposal_id, reason="requires design review",
                                   confirmation=f"REJECT paky-02 {proposal_id}")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.list_proposals()[0]["status"], "rejected")
        self.assertTrue(self.store._pending_file(proposal_id).exists())
        with self.assertRaisesRegex(ValueError, "Rejected proposal"):
            self.approve(proposal_id)
        with self.assertRaises(FileExistsError):
            self.store.reject(proposal_id, reason="again",
                              confirmation=f"REJECT paky-02 {proposal_id}")

    def test_recipe_and_chain_tampering_are_detected(self):
        first = self.queue_cognitive()["proposal_id"]
        self.approve(first)
        record_path = self.store._revision_dir("curiosita_gentile") / "rev-000001.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["expression"]["label"] = "Tampered"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        record_path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.store.history("curiosita_gentile")

    def test_chain_previous_hash_rejects_changed_earlier_revision(self):
        first = self.queue_cognitive()["proposal_id"]
        self.approve(first)
        edited = deepcopy(OPERATOR)
        edited["expression_id"] = "curiosita_gentile"
        second = self.store.queue(edited)["proposal_id"]
        self.approve(second, expected=1)
        path = self.store._revision_dir("curiosita_gentile") / "rev-000001.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["actor_kind"] = "explicit_local_cli_action"
        record["created_at_utc"] = "2026-10-26T00:00:00Z"
        path.write_text(json.dumps(record), encoding="utf-8")
        path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "Broken catalog revision"):
            self.store.history("curiosita_gentile")

    def test_reject_untrusted_execution_fields_or_out_of_range_values(self):
        for patch in [
            {"hardware_execution_authorized": True},
            {"script": "os.system('do_not_execute')"},
        ]:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    self.store.queue({**deepcopy(PROPOSAL), **patch})
        invalid = deepcopy(OPERATOR)
        invalid["eyes"]["right"]["pupil_scale"] = 1000
        with self.assertRaises(ValueError):
            self.store.queue(invalid)
        self.assertFalse(self.path.exists())

    def test_symlink_and_permissive_storage_are_refused(self):
        private = Path(self.tmp.name) / "safe"
        private.mkdir(mode=0o700)
        unsafe = Path(self.tmp.name) / "catalog-link"
        unsafe.symlink_to(private, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            CatalogStore(unsafe, "paky-02").queue(deepcopy(PROPOSAL))
        open_dir = Path(self.tmp.name) / "wide"
        open_dir.mkdir(mode=0o700)
        open_dir.chmod(0o755)
        with self.assertRaises(PermissionError):
            CatalogStore(open_dir, "paky-02").queue(deepcopy(PROPOSAL))

    def test_private_record_permissions_cannot_be_relaxed(self):
        proposal_id = self.queue_cognitive()["proposal_id"]
        path = self.store._pending_file(proposal_id)
        path.chmod(0o644)
        with self.assertRaises(PermissionError):
            self.approve(proposal_id)
        self.assertEqual(self.store.list_catalog(), [])


if __name__ == "__main__":
    unittest.main()
