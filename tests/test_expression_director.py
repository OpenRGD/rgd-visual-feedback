"""Expression Director: timeline, replay, isolation and existing composer conformance."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from rgd_visual.expression_director import ExpressionDirector, MAX_GESTURE_IDS, STEP_SCHEMA
from rgd_visual.expression_packs import load_pack
from rgd_visual.eye_composition import compose_preview

ROOT = Path(__file__).resolve().parents[1]
SESSION = "1" * 32
G1 = "a" * 32
G2 = "b" * 32


def request(gid=G1, scene="friendly", when=10000):
    return {"gesture_id": gid, "scene": scene, "requested_monotonic_ms": when}


def frame(seq=0, now=10000, phase="speaking", *, req=None, voice_at=None,
          mic_at=None, gaze_at=10000, enabled=True, link="ready", robot="paky-01"):
    return {
        "schema_version": STEP_SCHEMA, "session_id": SESSION, "sequence": seq,
        "gesture_request": req,
        "composition": {
            "schema_version": "openrgd.visual.eye-compose-input.v0.1-candidate",
            "source_kind": "operator_synthetic_preview", "robot_id": robot,
            "now_monotonic_ms": now,
            "voice": {"phase": phase, "observed_monotonic_ms": now if voice_at is None else voice_at,
                      "capture_confirmed": phase == "listening", "playback_confirmed": phase == "speaking"},
            "microphone": {"state": "capturing" if phase == "listening" else "disabled",
                           "observed_monotonic_ms": now if mic_at is None else mic_at},
            "gaze": {"x": .22, "y": -.14, "observed_monotonic_ms": gaze_at},
            "display": {"eyes_enabled": enabled, "link_state": link, "reduced_motion": False},
            "gesture": None,
        },
    }


class DirectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack(ROOT / "packs/eyes/core-v0.1.json")

    def director(self, robot="paky-01", session=SESSION):
        return ExpressionDirector(self.pack, robot_id=robot, session_id=session)

    def test_unchanged_composer_output_and_input(self):
        d = self.director()
        f = frame(req=request())
        before = deepcopy(f)
        r = d.step(f)
        self.assertEqual(r["gesture_decision"], "admitted")
        expected = deepcopy(f["composition"])
        expected["gesture"] = {"gesture_id": G1, "scene": "friendly", "started_monotonic_ms": 10000}
        self.assertEqual(r["composition"], compose_preview(self.pack, expected))
        self.assertEqual(f, before)
        self.assertFalse(r["hardware_commands_sent"])
        self.assertFalse(r["physical_output_observed"])
        self.assertFalse(r["source_authenticated"])
        self.assertFalse(r["actuation_enabled"])
        self.assertTrue(r["preview_only"])
        self.assertTrue(r["non_actuating"])

    def test_heartbeat_and_duplicate_do_not_extend_duration(self):
        d = self.director()
        d.step(frame(req=request()))
        r = d.step(frame(1,10500,req=request(when=10500)))
        self.assertEqual(r["gesture_decision"], "duplicate_ignored")
        self.assertEqual(r["composition"]["social_overlay"]["remaining_ms"],1000)
        r = d.step(frame(2,11500))
        self.assertEqual(r["previous_gesture_transition"],"expired")
        self.assertIsNone(r["active_gesture_id"])
        self.assertEqual(r["ended_gesture_id"],G1)
        r = d.step(frame(3,11600,req=request(when=11600)))
        self.assertEqual(r["gesture_decision"], "duplicate_ignored")
        self.assertIsNone(r["active_gesture_id"])

    def test_expiry_restores_current_phase_not_original(self):
        d = self.director()
        d.step(frame(req=request()))
        r = d.step(frame(1,11000,"idle"))
        self.assertEqual(r["active_gesture_id"],G1)
        self.assertEqual(r["composition"]["ring_intent"]["color"],"#FFFFFF")
        r = d.step(frame(2,11500,"idle"))
        self.assertIsNone(r["composition"]["social_overlay"])
        self.assertEqual(r["composition"]["expression"]["expression_id"],"core_idle")

    def test_latest_compatible_replaces_without_queue(self):
        d = self.director()
        d.step(frame(req=request()))
        r=d.step(frame(1,10100,req=request(G2,"surprised",10100)))
        self.assertEqual(r["gesture_decision"],"admitted")
        self.assertEqual(r["previous_gesture_transition"],"replaced")
        self.assertEqual(r["ended_gesture_id"],G1)
        self.assertEqual(r["active_gesture_id"],G2)
        r=d.step(frame(2,10900))
        self.assertIsNone(r["active_gesture_id"])
        self.assertEqual(r["previous_gesture_transition"],"expired")

    def test_incompatible_request_consumed_but_does_not_replace(self):
        d=self.director()
        d.step(frame(req=request()))
        r=d.step(frame(1,10100,req=request(G2,"curious",10100)))
        self.assertEqual(r["gesture_decision"],"incompatible")
        self.assertEqual(r["active_gesture_id"],G1)
        r=d.step(frame(2,10200,"idle",req=request(G2,"curious",10200)))
        self.assertEqual(r["gesture_decision"],"duplicate_ignored")
        self.assertEqual(r["active_gesture_id"],G1)

    def test_error_off_disconnect_disable_interrupt_and_never_resume(self):
        for override in ({"phase":"error"},{"phase":"off"},{"phase":"boot"},
                         {"link":"lost"},{"enabled":False},{"phase":"listening"}):
            with self.subTest(override=override):
                d=self.director()
                d.step(frame(req=request()))
                r=d.step(frame(1,10100,**override))
                self.assertEqual(r["previous_gesture_transition"],"interrupted")
                self.assertIsNone(r["active_gesture_id"])
                r=d.step(frame(2,10200,req=request(when=10200)))
                self.assertEqual(r["gesture_decision"],"duplicate_ignored")
                self.assertIsNone(r["composition"]["social_overlay"])

    def test_eyes_disconnection_keeps_functional_ring(self):
        d=self.director()
        d.step(frame(req=request()))
        r=d.step(frame(1,10100,link="lost"))
        self.assertEqual(r["composition"]["eyes_scene"],"link_lost")
        self.assertEqual(r["composition"]["ring_intent"]["color"],"#00FF46")

    def test_repeated_source_sample_does_not_renew_voice_or_gaze(self):
        d=self.director()
        d.step(frame())
        r=d.step(frame(1,10701,voice_at=10000,mic_at=10000))
        self.assertEqual(r["composition"]["gaze_status"],"expired_centered")
        self.assertEqual(r["composition"]["expression"]["eyes"]["left"]["gaze_x"],0)
        r=d.step(frame(2,12001,voice_at=10000,mic_at=10000))
        self.assertFalse(r["composition"]["voice_sample_current"])
        self.assertEqual(r["composition"]["functional_scene"],"connecting")
        self.assertEqual(r["composition"]["ring_intent"]["brightness"],0)

    def test_stale_mic_suppresses_listening(self):
        d=self.director()
        d.step(frame(phase="listening"))
        r=d.step(frame(1,12001,"listening",mic_at=10000))
        self.assertEqual(r["composition"]["functional_scene"],"connecting")
        self.assertEqual(r["composition"]["microphone_state"],"unknown")

    def test_regressed_conflicting_or_withdrawn_samples_fail_atomically(self):
        d=self.director()
        d.step(frame(req=request()))
        for stream in ("voice","microphone","gaze"):
            for mutation in ("regressed","conflict"):
                f=frame(1,10100,req=request(G2,"friendly",10100))
                field=f["composition"][stream]
                field["observed_monotonic_ms"]=9999 if mutation=="regressed" else 10000
                if mutation=="conflict":
                    if stream=="voice": field["playback_confirmed"]=False
                    if stream=="microphone": field["state"]="unknown"
                    if stream=="gaze": field["x"]=0.1
                with self.subTest(stream=stream,mutation=mutation),self.assertRaises(ValueError):
                    d.step(f)
        f=frame(1,10100)
        f["composition"]["gaze"]=None
        d.step(f)
        with self.assertRaises(ValueError):
            d.step(frame(2,10200))
        r=d.step(frame(2,10200,req=request(G2,"friendly",10200),gaze_at=10200))
        self.assertEqual(r["gesture_decision"],"admitted")
        self.assertEqual(r["seen_gesture_count"],2)

    def test_sequence_clock_session_and_robot_isolation(self):
        d=self.director()
        d.step(frame())
        bad=[frame(),frame(1,9999,gaze_at=9999),
             dict(frame(1,10100),session_id="2"*32),
             frame(1,10100,robot="paky-02"),
             dict(frame(1,10100),sequence=True)]
        for f in bad:
            with self.subTest(f=f),self.assertRaises(ValueError):
                d.step(f)
        self.assertEqual(d.step(frame(1,10100))["sequence"],1)
        self.assertEqual(self.director("paky-02").step(frame(robot="paky-02"))["robot_id"],"paky-02")

    def test_late_expired_and_incompatible_ids_are_not_admitted_later(self):
        d=self.director()
        r=d.step(frame(0,12000,req=request(when=10000)))
        self.assertEqual(r["gesture_decision"],"expired_request")
        r=d.step(frame(1,12100,req=request(G2,"friendly",11999)))
        self.assertEqual(r["gesture_decision"],"late_request")
        r=d.step(frame(2,12200,req=request(G2,"friendly",12200)))
        self.assertEqual(r["gesture_decision"],"duplicate_ignored")

    def test_id_capacity_never_evicts_and_functional_state_keeps_working(self):
        d=self.director()
        for i in range(MAX_GESTURE_IDS):
            r=d.step(frame(i,10000+i,req=request(f"{i:032x}","curious",10000+i)))
            self.assertEqual(r["gesture_decision"],"incompatible")
        r=d.step(frame(MAX_GESTURE_IDS,11000,"idle",req=request(G1,"friendly",11000)))
        self.assertEqual(r["gesture_decision"],"session_capacity_reached")
        self.assertEqual(r["seen_gesture_count"],MAX_GESTURE_IDS)
        self.assertEqual(r["composition"]["functional_scene"],"idle")
        r=d.step(frame(MAX_GESTURE_IDS+1,11100,"idle",req=request("0"*32,"friendly",11100)))
        self.assertEqual(r["gesture_decision"],"duplicate_ignored")

    def test_reject_live_ri_authority_and_direct_gesture(self):
        d=self.director()
        for data in ({"schema_version":"ri.consumer-observation-ref.v0.1-candidate"},
                     {"schema_version":"openrgd.visual.ri-status-report.v0.1-candidate"},
                     dict(frame(),hardware_commands_sent=True)):
            with self.assertRaises(ValueError):
                d.step(data)
        for key,value in (("source_kind","live"),("gesture",{"scene":"friendly"}),
                          ("voice",{"phase":[],"observed_monotonic_ms":10000,
                                    "capture_confirmed":False,"playback_confirmed":False})):
            f=frame()
            f["composition"][key]=value
            with self.assertRaises(ValueError):
                d.step(f)
        self.assertEqual(d.step(frame())["sequence"],0)

    def test_pack_and_return_values_cannot_mutate_session(self):
        p=deepcopy(self.pack)
        d=ExpressionDirector(p,robot_id="paky-01",session_id=SESSION)
        r=d.step(frame(req=request()))
        r["composition"]["expression"]["eyes"]["left"]["openness"]=.12
        p["expressions"]["core_friendly"]["duration_ms"]=500
        r=d.step(frame(1,10700))
        self.assertEqual(r["composition"]["social_overlay"]["remaining_ms"],800)

    def test_cli_timeline_and_console_compatible_export(self):
        cmd=[sys.executable,str(ROOT/"scripts/expression_director_preview.py")]
        result=json.loads(subprocess.check_output(cmd,timeout=20))
        self.assertEqual(len(result),8)
        self.assertEqual(result[0]["gesture_decision"],"admitted")
        self.assertEqual(result[1]["gesture_decision"],"duplicate_ignored")
        self.assertEqual(result[3]["previous_gesture_transition"],"expired")
        self.assertEqual(result[5]["previous_gesture_transition"],"interrupted")
        self.assertEqual(result[6]["gesture_decision"],"duplicate_ignored")
        self.assertEqual(result[7]["composition"]["functional_scene"],"connecting")
        self.assertEqual(json.loads(subprocess.check_output(cmd+["--frame-index","0"],timeout=20)),
                         result[0]["composition"])


if __name__=="__main__":
    unittest.main()
