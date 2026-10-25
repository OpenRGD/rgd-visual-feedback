# Visual Feedback — Console integration boundary (proposal)

## Status

Visual Feedback v0.2.0 is operational on Paky-01, and the BLE control has been operator-confirmed. This proposal does **not** claim that the Console can already discover, install or configure Visual Feedback.

The GitHub repository `OpenRGD/rgd-console` currently has no files on its default branch; the operator's locally working Console must be reconciled/published separately before implementation is planned there.

## Contract for future module discovery

- Manifest: `module.openrgd.json`.
- Module ID: `org.openrgd.visual-feedback`.
- Version: `0.2.0` (describes the existing operational implementation, not a newly tested release).
- Manifest/registry contract: `0.1.0-candidate`, **proposal only**, aligned in spirit with Calibration's proposal-only manifest.
- Capabilities: `visual.state.set`, `visual.state.status`. 
- User states: `idle`, `listening`, `thinking`, `speaking`, `error`, `off`.
- Current implementation: same-user Unix socket at `$XDG_RUNTIME_DIR/paky01-visual-feedback.sock` with version-1 newline-delimited JSON. This path is a Paky-01 adapter detail, **not** a universal OpenRGD contract.
- Hardware binding (address, color, brightness, service details): stored in the local operator config; never embed a specific MAC address in a universal module contract.

## Console acceptance gates (future work)

1. Review and finalize Module Registry schema with the Console team; do not interpret this candidate manifest as an accepted schema.
2. Discover module metadata **without executing install scripts**, pairing BLE, or starting services.
3. Present adapter capabilities, dependencies, safety boundary, required permissions and operator opt-in before installation.
4. Install only after an explicit user action; restrict runtime to an unprivileged user service and same-user IPC.
5. Treat returned `accepted`/desired state separately from `applied` and **never** imply an observed LED state, an actuation permission, or robot safety.
6. Keep the 1 kHz Somatic Runtime, actuators and CAN buses entirely out of this integration.
7. Validate on Ubuntu 22.04 with a known-working BLE ring, service restart/disconnect tests, and explicit install/uninstall rollback before enabling the Console UI.

## Existing manual workflow

```bash
cd ~/openrgd/repos/paky01-visual-feedback
./scripts/install-user.sh
~/.local/bin/paky-led status
```

Current service users should not rerun installation only because this manifest exists.
