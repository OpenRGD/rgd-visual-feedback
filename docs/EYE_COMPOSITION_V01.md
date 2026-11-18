# VISUAL — Eye Composition Preview v0.1

**Status:** candidate / offline / non-actuating. Stacked on [Visual Feedback shared pack PR #8](https://github.com/OpenRGD/rgd-visual-feedback/pull/8). Implements a **tested subset** of the behavioral rules proposed in [Paky-01 eyes specification PR #7](https://github.com/italiarobotica/paky-01/pull/7), section 2–7. It does **not** add runtime transport, display pixels, physical blink control, device watchdog, login, live Cognitive requests or sensor attestations.

## Decision: Visual Feedback owns composition, not Console or hardware

```text
Voice state / microphone / playback / gaze / gesture / eye availability
     ↓ (future separately authenticated producer snapshots)
Visual Feedback:
    normalize & validate → functional phase → eligibility → social geometry
                        → current gaze → reduced-motion policy
     ↓ (candidate declarative scene)
  ╔═══════════════════════════╦═════════════════════════╗
  ║ display-independent eyes  ║ functional ring intent  ║
  ╚═══════════════════════════╩═════════════════════════╝
     ↓
Future PERIPH-owned display and ring adapters, after commissioning
```

The sample `openrgd.visual.eye-compose-input.v0.1-candidate` explicitly requires `source_kind:operator_synthetic_preview`, not a trusted source. The simulator's `capture_confirmed` and `playback_confirmed` are **operator-supplied fictional test fixtures**, not evidence that the microphone or Bose player was actually in a given state. New sources are **not allowed** on this interface by merely changing the field.

## Behavior actually implemented in this pure preview

- **Functional state** selects the canonical `core_*` expression and independent ring color (white/blue/purple/green/red/off) from the generic pack. Unknown or Voice-stale `>2000 ms` data becomes a neutral `connecting` eye scene with ring off; no false listening/speaking claim.
- `listening` requires a present, fresh microphone state of `capturing` and an explicit capture confirmation in the synthetic Voice snapshot. Otherwise `connecting`/ring off.
- `speaking` requires synthetic playback confirmation; microphone may independently say `disabled`. A verified microphone `disabled` or `unknown` is not silently changed to `capturing`.
- **Seven one-shot social gestures:** `welcome,friendly,curious,surprised,uncertain,ack,concern`. Only compatible functional phases allow them; error/off/boot/disconnected suppress them. Gestures change only eyelid openness, pupil scale and eyebrow tilt. **They never overwrite the functional palette/ring, microphone state, current gaze or blink settings.** The input has an ID and monotonic start timestamp; after the gesture recipe's `duration_ms`, composition immediately falls back to the **current** phase. This is not yet a stateful anti-replay gate.
- **Current gaze** replaces decorative gaze if the sample is `≤700 ms` old, with bounds `±0.6`. It suppresses decorative `scan` during that preview frame. Expired gaze returns to center, in the pure preview without implementing the proposed 350 ms interpolation.
- **Display isolation:** if the eye link is unavailable, eyes show `link_lost/connecting` while the independent, current ring intent is preserved. If eyes were disabled by configuration, the result marks **black-pixels intent** without claiming backlight off or powering a display. It does not clear or invent Voice state.
- Reduced-motion setting selects `still` for the preview, preserving functional information. The actual blink/scan animation and accessibility implementation remain future renderer work.

The output `openrgd.visual.eye-compose-result.v0.1-candidate` contains a **validated copy** of the composed expression and the existing normalized `eye_frame_plan`, plus descriptions, suppressed/expired statuses and `hardware_commands_sent:false`, `physical_output_observed:false`, `source_authenticated:false`. No catalog revision or device is changed.

## Consciously NOT implemented in this wave

- A real Voice producer may only emit **transitions** at present. A transition is not a fresh periodic snapshot; the future host-side sampler must provide trustworthy capture/playback evidence before any physical claim.
- No tracking of producer sessions/turn IDs: late playback events, barge-in and sequence ordering require real ingress/correlation tests, not a synthetic status flag.
- No host→ESP32 transport, handshake/boot ID, 250 ms snapshot cadence, 1500 ms device watchdog, physical sync, output enable enforcement or perceptual measurement.
- No Chronoscope text output, safety alarm authority, battery thresholds, physical microphone mute verification, exact blink timing or 20 Hz gaze loop.
- The 12 s limit in a persistent eye recipe is an **offline clip maximum**, not a runtime TTL. Time freshness in this preview is checked against explicitly provided monotonic sample ages only.
- No honest claim of internal emotional state. Labels describe how the robot **represents** its current behavior.

## Run offline, with no daemon changes

```bash
python3 scripts/eye_composition_preview.py \
  --input examples/expressions/eye-composition-speaking-friendly.synthetic.json \
  > ~/openrgd/visual-eye-compose-speaking.demo.json
```

Expect: functional `speaking`, `friendly` overlay visible, gaze on both eyes, independent green ring `#00FF46`, microphone `disabled`, and **all hardware flags false**. The file can be inspected in the Console's future browser-only Composition Preview panel; it is not a live state export.

## Regression/evidence labels

`tests/test_eye_composition.py` covers 14 unit test scenarios, including stale microphone/Voice, invalid synthetic authority, expired gestures, critical-error precedence, display-only loss, reduced motion, gaze and physical-output markers. Schema conformance runs in the existing optional JSON Schema CI. Tests are **offline**; none justify live display/Voice claims.

## Next phases

1. Visual Studio **pure browser viewer** of the canonical composer's JSON output; no duplicated policy engine.
2. Separate authenticated host ingress with producer, session, monotonic clock provenance, turn correlation, TTL/preemption and known display capabilities.
3. Separately reviewed Eye Renderer ↔ PERIPH transport with boot handshake, independently observed physical output and safe recovery.
4. Robot-specific binding/orientation/calibration in `italiarobotica/paky-01`, not the shared pack.

The universal `core-v0.1.json` pack stays unchanged; Paky-01's dated `paky01_*` prototype remains separately auditable. Do **not** merge this PR or deploy to the mini-PC's running daemon until parent contracts have been approved.
