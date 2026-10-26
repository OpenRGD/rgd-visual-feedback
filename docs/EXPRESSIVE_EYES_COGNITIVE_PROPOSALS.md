# Visual Effects Studio — Expressive Eyes / Cognitive Proposals v0.1

**Status:** Candidate declarative eye expression and **offline-only** preview. **No Cognitive System integration exists** in this PR. No mini-screen display hardware is connected. This PR is stacked on Visual Studio foundation PR #3 and Voice IPC PR #2; the existing Paky-01 BLE systemd daemon remains untouched.

## Core architectural choice

Visual Feedback Studio owns **the grammar of what a robot chooses to visually express**, not the robot's mind, true emotional state, or operating system.

An expression consists of:
- Open-vocabulary `expression_id` and `label`: new named combinations are allowed without changing a fixed `happy/sad` enum.
- `affect`: three *presentation parameters* (valence, arousal, intensity), each bounded. **Not measured internal feelings.**
- Independent left/right eye anatomy in normalized coordinates: lid openness, gaze x/y, pupil scale, brow tilt. This does not assume a screen resolution or driver.
- Bounded palette (iris/background/accent), ring brightness intent (max 40% for the candidate preview, **not** a real hardware luminance limit), blink interval/duration, safe motion primitives (`still/breathe/scan`), and short `duration_ms`.
- `preview_only=true`, `non_actuating=true`, `claims_emotion_as_internal_state=false`.

Schema: `contracts/eye-expression.v0.1-candidate.schema.json`.

An untrusted future cognitive producer wraps an expression in `contracts/cognitive-expression-proposal.v0.1-candidate.schema.json` with an explicit source, session/sequence and robot ID. This wrapper **can request only transient preview**; its claims of origin are declarative, **not authenticated**. The actual runtime ingress must check producer identity out-of-band before accepting anything.

## Proposal → renderer boundary

```text
[Future Cognitive System, not connected]
       proposes a new expressive recipe (never executable code)
                 |
            strict validation
                 |
         bounded candidate preview
                 |
    ┌────────────┴─────────────┐
    │                          │
Eye Renderer (normalized)  LED accent intent
    │                          │
Console two-mini-display    a hypothetical
simulator (browser-only)     ring palette
                 |
       optional operator review
                 |
  explicit save to local draft catalog
   (not approved runtime device policy)
```

The Python planner (`src/rgd_visual/expressions.py`) produces a normalized `openrgd.visual.eye-frame-plan.v0.1-candidate`, tagged `hardware_commands_sent=false`, `physical_output_observed=false` and with no storage side effects. No `eval`, user shader, dynamic Python module, arbitrary asset URL, network input, driver access, file-system writes or hardware permissions are accepted.

**Operator review before persistent catalog adoption** is separate from **future transient runtime rendering**. A future policy may choose to allow low-risk transient expressions automatically *after* renderer, PERIPH, rate-limit and display hardware verification. This initial wave cannot do so.

## Human-authored vs Cognitive-sourced expressions

- Operators can define and preview new expressions using the same grammar.
- Cognitive System may submit new names/parametric combinations, including ones no one pre-authored.
- Arbitrary generated SVG, HTML, Python, JS, GLSL, image URLs, credentials and runtime hardware commands are **not** part of this contract.
- Promotion to catalog requires explicit operator review, version, provenance and rollback; no self-mutating production scenes.
- A future arbitration layer must apply TTL/preemption so a cognitive cue never hides important status/error feedback; facial-expression creation is not a replacement for robot safety indicators.

## Eye screen rendering goals

The UI prototype renders **two virtual mini displays** (not a real screen driver), supporting independent eye asymmetry, brow positions, pupils/gaze and slow, reduced-motion-aware blinking. Display resolution/connection are delegated to PERIPH and display adapters later. No synchronization with actual gimbal/head motors is implied.

## Example and local offline verification

```bash
cd ~/openrgd/repos/paky01-visual-feedback
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
python3 scripts/preview_eyes.py
python3 scripts/preview_eyes.py --proposal examples/expressions/cognitive-meraviglia.proposal.json
```

Both fixtures represent a **synthetic Cognitive proposal** for a newly named `meraviglia_curiosa` expression on a possible Paky-02 display. No fabricated physical or cognitive event is claimed.

## Subsequent waves (Visual only)

**VISUAL-0.2B:** bind expressions into Visual Studio's logical scenes/zones through an additive scene-target type (no breaking change to v0.1).  
**VISUAL-0.2C:** implement preview eye animator as a reusable hardware-agnostic renderer with dimension-aware outputs and tested frame-time constraints.  
**VISUAL-0.2D:** controlled host-side cognitive proposal ingress, trusted producer identity and per-robot policy/TTL arbitration.  
**VISUAL-0.2E:** connect reviewed PERIPH-owned display adapters, measure actual screen behavior and document recovery/offline behavior.  
**VISUAL-0.2F:** operator catalog approval, versioning, undo and evidence-qualified status in Console.

No other repository's cognitive implementation is changed by this proposal.
