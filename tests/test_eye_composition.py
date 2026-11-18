"""Offline-only reference checks for eye composition. No devices opened."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import unittest

from rgd_visual.eye_composition import SCHEMA, compose_preview, validate_input
from rgd_visual.expression_packs import load_pack

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs/eyes/core-v0.1.json"


def sample(
    phase="idle", *,
    voice_age=0, capture=False, playback=False, mic_state="unknown",
    mic_age=0, link="ready", enabled=True, reduced=False,
    gaze=None, gesture=None, now=10000, robot="paky-01",
):
    return {
        "schema_version": SCHEMA,
        "robot_id": robot,
        "now_monotonic_ms": now,
        "source_kind": "operator_synthetic_preview",
        "voice": {
            "phase": phase, "observed_monotonic_ms": now - voice_age,
            "capture_confirmed": capture, "playback_confirmed": playback,
        },
        "display": {"link_state": link, "eyes_enabled": enabled, "reduced_motion": reduced},
        "microphone": None if mic_state is None else
            {"state": mic_state, "observed_monotonic_ms": now - mic_age},
        "gaze": gaze, "gesture": gesture,
    }


def gaze(now=10000, age=50, x=0.3, y=-0.1):
    return {"x": x, "y": y, "observed_monotonic_ms": now-age}


def gesture(scene="friendly", now=10000, age=100, id="a"*32):
    return {"scene": scene, "gesture_id": id, "started_monotonic_ms": now-age}


class EyeCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack(PACK)

    def test_idle_is_functional_scene_not_internal_emotion(self):
        r = compose_preview(self.pack, sample())
        self.assertEqual(r["functional_scene"], "idle")
        self.assertEqual(r["eyes_scene"], "idle")
        self.assertEqual(r["expression"]["expression_id"], "core_idle")
        self.assertEqual(r["ring_intent"]["color"], "#FFFFFF")
        self.assertFalse(r["hardware_commands_sent"])
        self.assertFalse(r["physical_output_observed"])
        self.assertFalse(r["source_authenticated"])
        self.assertFalse(r["eye_frame_plan"]["emotion_internal_state_verified"])

    def test_listening_requires_real_capture_evidence_in_fixture(self):
        active = compose_preview(self.pack, sample(
            "listening", capture=True, mic_state="capturing"))
        self.assertEqual(active["eyes_scene"], "listening")
        self.assertEqual(active["ring_intent"]["color"], "#0050FF")
        for missing in (
            sample("listening", capture=False, mic_state="capturing"),
            sample("listening", capture=True, mic_state="unknown"),
            sample("listening", capture=True, mic_state="capturing", mic_age=2001),
            sample("listening", capture=True, mic_state=None),
        ):
            with self.subTest(missing=missing):
                r = compose_preview(self.pack, missing)
                self.assertEqual(r["functional_scene"], "connecting")
                self.assertEqual(r["ring_intent"]["brightness"], 0)
                self.assertIn("listening_not_confirmed", r["reasons"])

    def test_speaking_requires_player_confirmation_but_not_microphone_capture(self):
        p = compose_preview(self.pack, sample(
            "speaking", playback=True, mic_state="disabled"))
        self.assertEqual(p["eyes_scene"], "speaking")
        self.assertEqual(p["ring_intent"]["color"], "#00FF46")
        self.assertEqual(p["microphone_state"], "disabled")
        absent = compose_preview(self.pack, sample(
            "speaking", playback=False, mic_state="capturing"))
        self.assertEqual(absent["functional_scene"], "connecting")
        self.assertEqual(absent["ring_intent"]["brightness"], 0)

    def test_social_overlay_preserves_voice_color_gaze_and_source_recipe(self):
        pack_original = json.dumps(self.pack, sort_keys=True)
        source = sample("speaking", playback=True, mic_state="disabled",
                        gaze=gaze(x=-0.23,y=0.15), gesture=gesture("friendly"))
        copy = deepcopy(source)
        p = compose_preview(self.pack, source)
        self.assertEqual(p["eyes_scene"], "speaking")
        self.assertEqual(p["gesture_status"], "visible")
        self.assertEqual(p["social_overlay"]["scene"], "friendly")
        self.assertEqual(p["ring_intent"]["color"], "#00FF46")
        self.assertEqual(p["expression"]["palette"]["accent"], "#00FF46")
        self.assertEqual(p["expression"]["eyes"]["left"]["openness"],
                         self.pack["expressions"]["core_friendly"]["eyes"]["left"]["openness"])
        self.assertEqual(p["expression"]["eyes"]["left"]["gaze_x"], -0.23)
        self.assertEqual(p["expression"]["eyes"]["right"]["gaze_y"], 0.15)
        self.assertEqual(p["microphone_state"], "disabled")
        self.assertEqual(source, copy)
        self.assertEqual(json.dumps(self.pack, sort_keys=True), pack_original)

    def test_gesture_expires_and_restores_current_phase_not_old_phase(self):
        old = compose_preview(self.pack, sample("speaking", playback=True, gesture=gesture("friendly",age=1501)))
        self.assertEqual(old["gesture_status"], "expired")
        self.assertEqual(old["functional_scene"], "speaking")
        self.assertEqual(old["expression"]["eyes"]["left"]["openness"], 0.86)
        switched = compose_preview(self.pack, sample("idle", gesture=gesture("friendly",age=1600)))
        self.assertEqual(switched["functional_scene"], "idle")
        self.assertEqual(switched["gesture_status"], "expired")
        self.assertEqual(switched["expression"]["expression_id"], "core_idle")
        # Two different gestures may be evaluated by caller independently;
        # this stateless preview does NOT implement a replay gate or a queue.

    def test_error_off_and_link_conditions_suppress_social(self):
        for phase, reason in (("error","error"),("off","off"),("boot","boot")):
            p=compose_preview(self.pack, sample(phase,gesture=gesture("friendly")))
            self.assertEqual(p["eyes_scene"], reason)
            self.assertEqual(p["gesture_status"], "suppressed")
        p=compose_preview(self.pack,sample("speaking",playback=True,link="lost",gesture=gesture("friendly")))
        self.assertEqual(p["eyes_scene"], "link_lost")
        self.assertEqual(p["gesture_status"], "suppressed")
        self.assertEqual(p["ring_intent"]["color"], "#00FF46")

    def test_compatibility_prevents_social_in_wrong_phase(self):
        wrong=compose_preview(self.pack,sample("listening",capture=True,mic_state="capturing",
                                              gesture=gesture("friendly")))
        self.assertEqual(wrong["gesture_status"], "suppressed")
        ack=compose_preview(self.pack,sample("listening",capture=True,mic_state="capturing",
                                            gesture=gesture("ack")))
        self.assertEqual(ack["gesture_status"], "visible")
        self.assertEqual(ack["ring_intent"]["color"], "#0050FF")
        self.assertEqual(ack["expression"]["palette"]["iris"], "#0050FF")

    def test_gaze_expiry_does_not_repeat_old_target(self):
        r=compose_preview(self.pack,sample("thinking",gaze=gaze(x=0.2,y=0.1)))
        self.assertEqual(r["gaze_status"],"applied_in_preview")
        self.assertEqual(r["expression"]["animation"]["mode"],"still")
        self.assertEqual(r["expression"]["eyes"]["left"]["gaze_x"],0.2)
        expired=compose_preview(self.pack,sample("thinking",gaze=gaze(age=701)))
        self.assertEqual(expired["gaze_status"],"expired_centered")
        self.assertEqual(expired["expression"]["eyes"]["left"]["gaze_x"],0)

    def test_stale_voice_falls_back_without_fabricating_speaking(self):
        p=compose_preview(self.pack,sample("speaking",voice_age=2001,playback=True))
        self.assertEqual(p["functional_scene"],"connecting")
        self.assertEqual(p["ring_intent"]["color"],"#000000")
        self.assertFalse(p["voice_sample_current"])
        self.assertIn("voice_unknown_or_stale",p["reasons"])
        missing=sample("speaking",playback=True)
        missing["voice"]=None
        self.assertEqual(compose_preview(self.pack,missing)["functional_scene"],"connecting")

    def test_eyes_disabled_is_independent_from_voice_ring(self):
        p=compose_preview(self.pack,sample("speaking",playback=True,enabled=False,
                                           gesture=gesture("friendly")))
        self.assertTrue(p["eyes_disabled"])
        self.assertTrue(p["blank_pixels_intent"])
        self.assertEqual(p["eyes_scene"],"off")
        self.assertEqual(p["ring_intent"]["color"],"#00FF46")
        self.assertEqual(p["gesture_status"],"suppressed")
        self.assertFalse(p["hardware_commands_sent"])

    def test_reduced_motion_suppresses_decorative_animation_not_functional_scene(self):
        p=compose_preview(self.pack,sample("idle",reduced=True))
        self.assertEqual(p["eyes_scene"],"idle")
        self.assertEqual(p["expression"]["animation"]["mode"],"still")
        self.assertEqual(p["ring_intent"]["color"],"#FFFFFF")

    def test_cross_robot_pack_reuse_and_input_checks(self):
        for robot in ("paky-01","paky-02","demo-robot"):
            p=compose_preview(self.pack,sample(robot=robot))
            self.assertEqual(p["robot_id"],robot)
        for bad in (
            {"source_kind":"network_trusted"},
            {"robot_id":"../../not-a-robot"},
            {"display":{"link_state":"ready","eyes_enabled":"false","reduced_motion":False}},
            {"gaze":{"x":10,"y":0,"observed_monotonic_ms":9999}},
            {"now_monotonic_ms":True},
            {"hardware_commands_sent":True},
        ):
            with self.subTest(bad=bad):
                data=sample()
                data.update(bad)
                with self.assertRaises(ValueError):
                    validate_input(data)

    def test_future_and_invalid_gesture_refused(self):
        for mutation in (
            {"voice":{"phase":"listening","observed_monotonic_ms":10001,
                      "capture_confirmed":True,"playback_confirmed":False}},
            {"gesture":{"scene":"friendly","gesture_id":"not-a-id",
                         "started_monotonic_ms":9900}},
            {"gesture":{"scene":"eval_code","gesture_id":"a"*32,
                         "started_monotonic_ms":9900}},
        ):
            with self.subTest(mutation=mutation):
                data=sample()
                data.update(mutation)
                with self.assertRaises(ValueError):
                    validate_input(data)

    def test_gesture_does_not_change_functional_ring_when_idle(self):
        p=compose_preview(self.pack,sample("idle",gesture=gesture("surprised")))
        self.assertEqual(p["gesture_status"],"visible")
        self.assertEqual(p["ring_intent"]["color"],"#FFFFFF")
        self.assertEqual(p["expression"]["palette"]["iris"],"#FFFFFF")
        self.assertEqual(p["expression"]["eyes"]["left"]["openness"],1)


if __name__=="__main__":
    unittest.main()
