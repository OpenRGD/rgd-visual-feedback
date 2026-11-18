# OpenRGD — Shared Eye Expression Pack v0.1

**Status: candidate / preview-only, robot-agnostic.** This is a proposed reusable **catalog of expressions**, not firmware, runtime arbitration, a screen adapter, or a claim of emotion.

## Ownership: one engine, one editor, multiple robot profiles

| Concern | Canonical owner |
| --- | --- |
| Eye expression grammar, catalog, validation and future state arbitration | **OpenRGD/rgd-visual-feedback** |
| UI for editing, previewing, comparing and exporting profiles | **OpenRGD/rgd-console**, Visual Effects Studio |
| Physical display placement, USB/SPI pinout, transforms and as-built acceptance | Each robot repository (e.g. **italiarobotica/paky-01**) |
| Approved catalogue revisions per robot | Visual Feedback's candidate catalog lifecycle; separate operator action |
| Rendered pixels/driver and hardware-specific physical binding | Future explicitly reviewed adapter; **not** Console |

The Console must **not** implement a second authoritative emotion/scene engine, live arbitration, permanent approval store or hardware driver. Browser validation and simulated rendering may exist for interactive editing but are not a source of truth for execution.

## Universal source

- `packs/eyes/core-v0.1.json`: **21 robot-neutral recipes**, 21 named scene bindings, 6 proposed ring styles, 6 Voice event mappings.
- `contracts/eye-pack.v0.1-candidate.schema.json`: strict candidate schema (embedded validated expression grammar, no network references).
- `src/rgd_visual/expression_packs.py`: strict validation and **pure** generation of per-robot Visual Studio preview profiles.
- `scripts/eye_pack_preview.py`: offline CLI with no hardware access.
- `tests/test_eye_packs.py`: checks strict inputs, source neutrality, multiple robot identities, no actuation and preview routing.

These are **reusable starting values**, not forced global behaviors or installed hardware claims. Italian labels currently mirror the initial design exercise; translation and alternative expression packs are future additive features.

### Generate a preview for any robot

From this repository (after `python -m pip install -e .`):

```bash
python scripts/eye_pack_preview.py --robot-id demo-robot > /tmp/demo-robot-eyes.preview.json
python scripts/eye_pack_preview.py --robot-id paky-01 --source voice --event listening.started
python scripts/eye_pack_preview.py --robot-id paky-02 --without-ring > /tmp/paky02-eyes.preview.json
```

All outputs explicitly set `preview_only:true` and `non_actuating:true` and all logical zones have `adapter_id:null` / `binding_status:planned`. The generated `robot_id` scopes the **preview file only**; the core pack remains unchanged. No robot is contacted. The default `face-ring` is a **virtual zone**, not the physical Miracles.Star ring.

The pack includes styles for `off`, `error`, etc. but cannot promise physical backlight control, safety interlocks, listening verification or real-time output. For operational guarantees see separate vetted runtime/transport work. Unknown audio state must not be rendered as confirmed listening in a live service.

## Migration from the Paky-01 design prototype

The first 21 numeric recipes were drafted in `italiarobotica/paky-01` ([Paky-01 #7](https://github.com/italiarobotica/paky-01/pull/7)). This platform pack preserves their values but renames identifiers from `paky01_*` to `core_*`. **No special-case Paky-01 logic is carried into this library.** The original hardware-specific profile remains a version-pinned *prototype* until its adoption/override path is explicitly reviewed; do not silently overwrite operator edits.

The Console prototype [#16](https://github.com/OpenRGD/rgd-console/pull/16) currently bundles a **fixed sample profile** for browser-only use. That pinned fixture is provisional and should be replaced by an explicit import/export of the generated, reviewed Visual Feedback profile when consolidating the stacked Console PRs, not by copying a second scene engine or maintaining two independently editable catalogs.

## Security & publication readiness

The repository is currently **private** on GitHub; don't assume it is already public. Before changing its visibility, audit deployment examples/config and BLE identifiers, historical commits, licensing and any operator-specific data. This candidate pack contains no Bluetooth address, personal data, hardware pinout or robot-specific identity.

## Review gates

1. Merge candidate generic pack only after Visual Feedback schema/Studio prerequisite PRs have been reviewed.
2. Validate in CI and use the Console as a renderer/editor of previews; keep backend validation as canonical.
3. Add signed/authorized import and per-robot approval path before persistent adoption.
4. Implement a separate device/ESP32 adapter and physically verify it before enabling real outputs.
