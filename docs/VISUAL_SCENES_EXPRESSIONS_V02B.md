# VISUAL-0.2B — Expression Catalog + Scene Targets (candidate, offline preview)

**Date:** 2026-10-26. **Status:** draft implementation, not merged or deployed. No changes to Paky-01's BLE systemd service, Voice Studio, physical eyes or PERIPH.

## Version compatibility

- **`openrgd.visual-studio.profile.v0.1-candidate`** and its original strict `contracts/visual-studio-profile.v0.1-candidate.schema.json` are left unchanged. Existing Paky-01 RGB profiles still validate, and their preview LED results retain `effect/color/brightness` fields.
- **`openrgd.visual-studio.profile.v0.2-candidate`** is an opt-in format. It adds a bounded **profile-local `expressions` catalog** of declarative `openrgd.visual.eye-expression.v0.1-candidate` recipes (up to 32).
- Each v0.2 scene output may be a legacy light target `{"zone_id","effect","color","brightness"}` or an expressive display target `{"zone_id","effect":"eye_expression","expression_id"}`. The latter references a recipe by name; it does **not** place executable code, RGB pixel buffers, screen dimensions, firmware or BLE addresses into the scene.
- Logical zone capabilities gain `eye_expression` only in v0.2. Hardware output remains **planned** unless independently authorized and commissioned.
- Existing `preview(profile,source,event)` now dispatches the typed eye target to the previously tested, *pure* `plan_eye_preview()` and returns a nested virtual frame plan. Both subplans and whole result retain `hardware_commands_sent:false`, `physical_output_observed:false`, `preview_only:true`.

## Catalog lifecycle

1. **Author or propose.** Operator or a future Cognitive producer creates a new named expression as bounded numeric parameters; no code change required. A `cognitive_proposal` has no authenticated identity nor execution authority in v0.2B.
2. **Preview.** The parser validates open names, gaze, pupil, palette, blink, duration and non-actuating flags. `Paky-02` fixture shows a single `welcome` scene combining an RGB ring, future room light and two expressive mini displays, with the display zone clearly **planned**.
3. **Review/Stage.** Visual Studio may stage an expression into the *local browser draft* catalog, and only on explicit operator action assign it to a scene. The Python `stage_expression_preview(profile, candidate, scene)` API does the same for a COPY of a v0.2 profile, with bounds, robot identity checks and no disk writes. A Cognitive-sourced expression must arrive in the complete candidate proposal envelope; a standalone recipe with `origin:cognitive_proposal` is rejected. Browser localStorage is **not** the robot's persistent catalog or trusted policy store.
4. **Apply later.** A later wave must define a separately permissioned durable catalog with review/revision/rollback, source identity/authentication, TTL/arbitration, physical PERIPH bindings and verified display hardware.

The current expression recipe's `origin` records its proposed provenance, not approval or trust. A Cognitive proposal that has been validated may be used for preview only; it cannot silently update scenes or install itself.

## Operator-only offline smoke

Run on an independent checkout/worktree with the v0.2B branch, **not by switching the live Visual daemon's directory**:

```bash
python3 scripts/studio_preview.py --profile profiles/paky02-expressive-studio.preview.json --source system --event operator.welcome
python3 scripts/stage_expression_preview.py --profile profiles/paky02-expressive-studio.preview.json --proposal examples/expressions/cognitive-curiosita-gentile.proposal.json --scene welcome
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

The first output contains RGB, room light and eye frame intents. The second prints a candidate updated profile and marks persistence/hardware execution as false. All outputs are simulated. No physical devices are opened or files written. The second candidate introduces the entirely new name `curiosita_gentile`, proving that expressive names can be added as data without changing the Python engine.

## Next wave

The Console Visual Effects Studio v0.2B must offer an explicit **Stage Expression in Scene (draft only)** action, and an integrated preview for each output type. No new API route, host relay, registry installer or automatic hardware command should be introduced at this stage.

An expression named `meraviglia_curiosa` is a representation choice; it does not certify the robot experiences that emotion.
