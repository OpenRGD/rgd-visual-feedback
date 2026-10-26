# OpenRGD Visual Effects Studio — v0.1 candidate

**Status:** pure configuration + deterministic preview. **No device controls, installer, REST API, MQTT, runtime scene switching, safety authority, or physically tested animations.** Based on the already operator-verified Paky-01 Visual Feedback v0.3 candidate. The current v0.3 user service and BLE adapter remain unchanged.

## Architectural boundary

```text
Voice Studio     Vision     Somatic read-only state     Operator / system
       \            |            /                          /
         event adapters — bounded, explicit, source-tagged
                              |
                   [future event arbiter]
                              |
                  matching rules / policies
                              |
                      scene + zone intents
                              |
              capability & permission check
                   /          |             \
             BLE adapter   USB/serial      home/room API
```

The matching contract is **independent** from capture devices, output speakers, LED addresses, BLE/MQTT transport and physical robot variants. Input events are domain names, not direct device calls. The existing voice socket can later normalize source=rgd-voice/event=playback.started into `source=voice,event=playback.started`; this is not wired to runtime yet.

## Artifact ownership

- `profiles/paky01-studio.preview.json`: example robot-scoped policy, not installed runtime config. No MAC addresses or cloud keys.
- `contracts/visual-studio-profile.v0.1-candidate.schema.json`: strict candidate scene/mapping format. Not accepted as canonical RGD.
- `src/rgd_visual/studio.py`: offline deterministic matching, mapping priority and fallback, rejects malformed references and unsafe profile claims.
- `scripts/studio_preview.py`: prints a hypothetical result, never dispatches it.
- `tests/test_studio.py`: zero-device scenario and negative checks.

Current scene names are the logical UI states `idle/listening/thinking/speaking/error/off`, plus `welcome`. Effects declared here: `solid`, `pulse`, `chase`, `wave`. **Only `solid` was operator-verified on Paky-01's BLE ring.** Others are design vocabulary, not supported hardware capabilities until separately verified.

## Run a preview locally

```bash
cd ~/openrgd/repos/paky01-visual-feedback
python3 scripts/studio_preview.py --source voice --event playback.started
python3 scripts/studio_preview.py --source system --event operator.welcome
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

The CLI only reads JSON and prints selected scenes; it does **not** change what the ring displays.

## Future Visual Studio operator workspace

The Console can offer a local simulated editor: Sources → Mappings → Scenes → Zones → Preview. The frontend MUST prominently label previews as synthetic; browser-only choices cannot directly call BLE. Exported profiles are proposals until host-side validation, permissions and explicit deployment.

## Next implementation gates

1. **Rules**: create a reviewed v0.2 arbitration policy for concurrent sources (voice/browser, power alerts, perception), priority, TTL/expiry, cooldown and absence of data. Never let a synthetic preview or low-priority event suppress a genuine operator error indefinitely.
2. **Zones**: declare capabilities per hardware adapter and fail closed on unsupported effects. Never derive electric ratings or possible brightness/flicker limits from the manifest.
3. **Adapters**: implement explicit interfaces for existing BLE solid states, then USB addressable pixels, Wi-Fi room lamps and optional MQTT topics *only after authorization and credential isolation*.
4. **Remote outputs**: no network calls, discovery or remote pairing from browser. An authenticated host-side relay owns external light control and reports desired/applied/observed separately.
5. **Safety/comfort**: cap brightness by installation, respect user reduced-motion settings, prohibit unreviewed strobe/high-frequency flashes, declare photosensitivity limits, and rate-limit updates. LEDs never replace E-stop or safety controls.
6. **Physical test**: output should follow *real* event callbacks; missing devices and disconnections must leave voice and Somatic Runtime fully operational.
7. **Provisioning**: a Python user service is not a Cargo module. Update OpenRGD Registry and Console Module Agent in separately reviewed, pinned distribution/permission waves. Do not pretend this candidate profile is already installable by Console.

`matched:true`, `eligible_by_declared_capabilities:true` or a BLE `applied` status is **not** a sensor-certified observation of light output or robot readiness.
