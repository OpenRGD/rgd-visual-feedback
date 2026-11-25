"""Offline conformance and isolation tests; never open a hardware resource."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from rgd_visual.config import Settings
from rgd_visual.driver import MiraclesStarBLE
from rgd_visual.ri_report import MAX_INPUT_BYTES, decode_snapshot, project_status
from rgd_visual.voice_events import VoiceEventGate, SCHEMA as VOICE_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/ri"


def sample():
    return json.loads((FIX / "legacy-status.synthetic.json").read_text())


def project(s=None, kind="synthetic"):
    return project_status(sample() if s is None else s, input_kind=kind)


class ReportProjectionTests(unittest.TestCase):
    def test_desired_and_last_driver_ack_are_distinct(self):
        s = sample()
        original = deepcopy(s)
        r = project(s)
        self.assertEqual(s, original)
        report, voice = r["reports"]
        self.assertEqual(report["data"]["desired"], "speaking")
        self.assertEqual(report["data"]["applied"], "idle")
        self.assertTrue(report["data"]["driver_ack_reported"])
        self.assertIsNone(report["data"]["rendered_scene"])
        self.assertEqual(voice["data"]["event"], "playback.started")
        self.assertEqual(voice["data"]["sequence"], 7)
        self.assertEqual(voice["source_owner"], "rgd-voice")
        self.assertEqual(voice["reported_by"], "rgd-visual-feedback")

    def test_disconnected_and_pending_states_preserved(self):
        for connected in (False, True):
            s = sample()
            s.update(connected=connected, applied=None)
            d = project(s)["reports"][0]["data"]
            self.assertEqual(d["connected"], connected)
            self.assertIsNone(d["applied"])
            self.assertFalse(d["driver_ack_reported"])

    def test_no_event_yet_and_legacy_without_gate(self):
        s = sample()
        s["voice_event"].update(session_id=None, last_event=None, last_sequence=None)
        self.assertEqual(len(project(s)["reports"]), 1)
        del s["voice_event"]
        self.assertEqual(len(project(s)["reports"]), 1)

    def test_redaction_no_address_or_raw_error(self):
        s = sample()
        s["address"] = "11:22:33:44:55:66"
        s["last_error"] = "private raw error path and token"
        r = project(s)
        self.assertTrue(r["reports"][0]["data"]["error_reported"])
        encoded = json.dumps(r)
        self.assertNotIn(s["address"], encoded)
        self.assertNotIn(s["last_error"], encoded)
        self.assertNotIn('"address"', encoded)
        self.assertNotIn('"last_error"', encoded)

    def test_no_freshness_or_authority_even_when_applied_matches(self):
        s = sample()
        s["applied"] = s["desired"]
        for kind in ("unverified_snapshot", "synthetic", "replay"):
            r = project(s, kind)
            self.assertEqual(r["input_kind"], kind)
            self.assertEqual(r["freshness"], "unknown")
            for flag in ("source_authenticated", "robot_binding_verified", "physical_output_observed",
                         "history_committed", "actuation_enabled", "may_drive_visual"):
                self.assertIs(r[flag], False)
            self.assertIsNone(r["physical_observation_ref"])
            for report in r["reports"]:
                self.assertIsNone(report["occurred_at"])
                self.assertIsNone(report["clock_domain_id"])
            self.assertTrue(r["non_actuating"])
        with self.assertRaises(ValueError):
            project(s, "live")

    def test_no_replay_restamping(self):
        a = project(kind="replay")
        b = project(kind="replay")
        self.assertEqual(a, b)
        self.assertNotIn("observation_id", a)

    def test_refuses_failed_or_inconsistent_status(self):
        for patch in ({"ok": False}, {"connected": False}, {"desired": "unknown"},
                      {"applied": "unknown"}, {"connected": 1}, {"last_error": 42},
                      {"address": "invalid"}, {"adapter": "other"}, {"physical_output_observed": True},
                      {"command": "set_state"}, {"schema_version": "other"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                project(dict(sample(), **patch))

    def test_refuses_partial_or_forged_voice_status(self):
        for patch in ({"physical_event_verified": True}, {"last_sequence": True},
                      {"session_id": None}, {"last_event": "model.text.generated"},
                      {"last_sequence": -1}, {"source": "other"}, {"occurred_at": "fake"}):
            s = sample()
            s["voice_event"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                project(s)

    def test_refuses_observation_reference_and_composer_as_status(self):
        for value in (
            {"schema_version": "ri.consumer-observation-ref.v0.1-candidate",
             "observation_id": "obs_" + "0"*32},
            {"schema_version": "openrgd.visual.eye-compose-result.v0.1-candidate",
             "preview_only": True, "hardware_commands_sent": False},
            {"version": 1, "command": "voice_event"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                project(value)

    def test_real_status_shape_without_hardware_or_gate_mutation(self):
        # Only construct the driver object; never start its run() coroutine.
        adapter = MiraclesStarBLE(Settings("00:00:00:00:00:00", dict.fromkeys(
            ("idle", "listening", "thinking", "speaking", "error", "off"))))
        gate = VoiceEventGate()
        gate.consume({"version": 1, "command": "voice_event", "schema_version": VOICE_SCHEMA,
                      "source": "rgd-voice", "session_id": "1"*32,
                      "sequence": 2, "event": "playback.started"}, adapter)
        old = adapter.status(), gate.status(), adapter.revision
        r = project_status({"ok": True, **old[0], "voice_event": old[1]}, input_kind="synthetic")
        self.assertEqual(old, (adapter.status(), gate.status(), adapter.revision))
        self.assertEqual(r["reports"][0]["data"]["desired"], "speaking")
        self.assertIsNone(r["reports"][0]["data"]["applied"])
        self.assertEqual(r["reports"][1]["data"]["sequence"], 2)

    def test_bounded_decoder_and_duplicate_keys(self):
        for raw in (b"", b" "* (MAX_INPUT_BYTES + 1), b"[]", b'{"ok":true,"ok":false}',
                    b'{"voice_event":{"source":"a","source":"b"}}', b"\xff"):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                decode_snapshot(raw)

    def test_cli_success_and_failure_are_standalone(self):
        cmd = [sys.executable, "-m", "rgd_visual.ri_report", "--input-kind", "synthetic"]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        good = subprocess.run(cmd, input=json.dumps(sample()).encode(), capture_output=True, env=env, timeout=10)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout), project())
        bad = subprocess.run(cmd, input=b'{"secret":"private-token"}', capture_output=True, env=env, timeout=10)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(bad.stdout, b"")
        self.assertNotIn(b"private-token", bad.stderr)


class PinnedContractTests(unittest.TestCase):
    def setUp(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("Dedicated VISUAL-RI-01 candidate CI installs jsonschema")
        self.Validator = Draft202012Validator

    def validator(self, p):
        schema = json.loads(p.read_text())
        self.Validator.check_schema(schema)
        return self.Validator(schema)

    def test_pinned_source_schema_blobs(self):
        for file, expected in (
            ("consumer-observation-ref.pinned.schema.json", "3d92e074e71593bf6db0a735394c628ea131668d"),
            ("core-feedback-delivery.pinned.schema.json", "c041efa70c221edde09a3025b7c914c765ad7ab5"),
        ):
            raw = (FIX / file).read_bytes()
            git_blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
            self.assertEqual(hashlib.sha1(git_blob).hexdigest(), expected, file)

    def test_local_candidate_schema_and_negative_authority(self):
        v = self.validator(ROOT / "contracts/ri-status-report.v0.1-candidate.schema.json")
        for kind in ("synthetic", "replay", "unverified_snapshot"):
            self.assertTrue(v.is_valid(project(kind=kind)))
        for patch in ({"physical_output_observed": True}, {"actuation_enabled": True},
                      {"source_authenticated": True}, {"freshness": "fresh"},
                      {"may_drive_visual": True}, {"history_committed": True}):
            self.assertFalse(v.is_valid(dict(project(), **patch)))
        s = project()
        s["reports"][0]["occurred_at"] = "2026-11-25T00:00:00Z"
        self.assertFalse(v.is_valid(s))
        s = project()
        s["reports"][0]["data"]["driver_ack_reported"] = False
        self.assertFalse(v.is_valid(s))
        s = project()
        s["reports"][0]["data"]["address"] = "00:00:00:00:00:00"
        self.assertFalse(v.is_valid(s))

    def test_output_is_neither_ri_observation_ref_nor_core_delivery(self):
        # These are exact upstream candidate schemas, not copied runtime validators.
        r = project()
        for file in ("consumer-observation-ref.pinned.schema.json",
                     "core-feedback-delivery.pinned.schema.json"):
            v = self.validator(FIX / file)
            for obj in [r, *r["reports"]]:
                self.assertFalse(v.is_valid(obj), file)
        # A genuine conforming RI reference still has no lifecycle/gaze authority here.
        ref = {
            "schema_version": "ri.consumer-observation-ref.v0.1-candidate",
            "observation_id": "obs_" + "1"*32,
            "source_id": "source.synthetic.camera", "modality": "rgb",
            "reference_frame_id": "frame.camera.synthetic", "sample_sequence": 1,
            "payload_sha256_hex": "a"*64, "payload_media_type": "image/jpeg",
            "payload_size_bytes": 10, "origin_status": "source_declared_simulated",
            "integrity_status": "verified_local_hash", "source_verified": False,
            "robot_binding_verified": False, "history_committed": False, "actuation_enabled": False,
            "time": {"clock_domain_id": "host.synthetic.boot", "boot_id": "fixture",
                     "received_monotonic_ns": 1234, "source_time_status": "unknown",
                     "source_measurement_time": None, "chronograf_anchor_ref": None},
        }
        self.assertTrue(self.validator(FIX / "consumer-observation-ref.pinned.schema.json").is_valid(ref))
        with self.assertRaises(ValueError):
            project(ref)


if __name__ == "__main__":
    unittest.main()
