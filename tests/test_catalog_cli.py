"""Subprocess CLI smoke: no provider traffic, Bluetooth, daemon or physical output."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/visual_catalog.py"
FIXTURE = ROOT / "examples/expressions/cognitive-curiosita-gentile.proposal.json"


class CatalogCLITests(unittest.TestCase):
    def test_queue_approve_reject_guard_and_latest_history(self):
        with tempfile.TemporaryDirectory(prefix="rgd-visual-cli-test-") as temp:
            root = Path(temp) / "catalog"
            args = [sys.executable, str(CLI), "--robot", "paky-02", "--root", str(root)]

            def run(*parts, success=True):
                result = subprocess.run(
                    [*args, *parts], capture_output=True, text=True,
                    timeout=8, check=False,
                )
                if success:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return json.loads(result.stdout)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("CATALOG ERROR", result.stderr)
                return result

            self.assertEqual(run("list"), [])
            pending = run("queue", "--file", str(FIXTURE))
            proposal_id = pending["proposal_id"]
            self.assertFalse(pending["hardware_commands_sent"])
            self.assertEqual(run("pending")[0]["status"], "pending")
            run("approve", "--proposal", proposal_id, "--expected-revision", "0",
                "--confirm", "NO", success=False)
            self.assertEqual(run("list"), [])
            approved = run("approve", "--proposal", proposal_id, "--expected-revision", "0",
                           "--confirm", f"APPROVE paky-02 {proposal_id}")
            self.assertEqual(approved["revision"], 1)
            self.assertFalse(approved["hardware_execution_authorized"])
            versions = run("history", "--expression", "curiosita_gentile")
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0]["expression"]["label"], "Curiosità gentile")
            self.assertEqual(run("pending")[0]["status"], "approved")
            run("rollback", "--expression", "curiosita_gentile", "--to-revision", "1",
                "--expected-revision", "1",
                "--confirm", "ROLLBACK paky-02 curiosita_gentile TO 1", success=False)
            self.assertEqual(len(run("history", "--expression", "curiosita_gentile")), 1)


if __name__ == "__main__":
    unittest.main()
