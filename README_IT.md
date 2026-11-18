# OpenRGD — Paky-01 Visual Feedback v0.2

**Visual Feedback v0.2 physically validated by the Paky-01 operator (2026-10-25)**: BLE color changes, CLI states and Ubuntu user service reported working. The optional v0.3 voice lifecycle IPC addition is **candidate-only**, has synthetic tests, and is not yet deployed or connected to actual Voice Studio events.

Optional voice-event ingress proposed in the separate v0.3 PR: see `docs/VOICE_IO_HOOK.md`. It does not change the v0.2 installation until explicitly updated.

Features:
- Single-owner BLE connection + reconnection every ~3 seconds following discovery/connection errors.
- Unix-domain socket API (same-user local IPC only, no TCP port or HTTP server).
- Six configurable states: `idle`, `listening`, `thinking`, `speaking`, `error`, `off`.
- `paky-led` CLI, user-level systemd unit, log via journalctl.
- No actuator/CAN operations; no changes to Somatic Runtime.

## Installation on Paky-01 mini-PC (Ubuntu 22.04)

Unzip this package into a stable directory (do not move it after installation):

```bash
mkdir -p ~/openrgd/repos/paky01-visual-feedback
unzip -o ~/Downloads/paky01-visual-feedback-v0.2.zip -d ~/openrgd/repos/paky01-visual-feedback
cd ~/openrgd/repos/paky01-visual-feedback
./scripts/install-user.sh
```

This installer creates a local Python venv, installs Bleak in the venv (no setuptools/editable install needed), writes a user-only config file and a `systemd --user` service. It **will not overwrite an existing config**. It requires working package access from the mini-PC for `pip install bleak`. It does **not** use sudo or change Bluetooth/robot configuration.

Test:

```bash
~/.local/bin/paky-led status
~/.local/bin/paky-led listening
sleep 2
~/.local/bin/paky-led thinking
sleep 2
~/.local/bin/paky-led speaking
sleep 2
~/.local/bin/paky-led idle
```

The public example uses the non-operational BLE address `00:00:00:00:00:00`. Before a first installation, set the **real device address only in** `~/.config/paky-visual-feedback/config.json` (private per-host configuration, mode 0600). Existing installed configurations are preserved by the installer. The physical Paky-01 BLE identifier belongs to the private instance inventory, not the generic OpenRGD adapter documentation.

Check service:

```bash
systemctl --user status paky01-visual-feedback --no-pager
journalctl --user -u paky01-visual-feedback -n 60 --no-pager
```

Config file: `~/.config/paky-visual-feedback/config.json` (color `#RRGGBB`, brightness 0..100). After edits:

```bash
systemctl --user restart paky01-visual-feedback
```

Stop the service:

```bash
systemctl --user disable --now paky01-visual-feedback
```

Full uninstall of service and CLI (keeps config and source for recovery): `./scripts/uninstall-user.sh`.

## Notes

- Keep Miracles.Star disconnected while the service owns BLE.
- CLI response `accepted:true` is asynchronous; check `applied` in `status` for actual command success. It does not prove LED visual output.
- When adapter is unavailable, service keeps desired state and replays it on reconnect.
- The service starts with user session; enabling pre-login start needs separate review of linger behavior.
- Power from USB remains unchanged; this package talks over Bluetooth.
- No changes were made to git remotes or to the running mini-PC by preparing this archive.
- Next step: connect real Voice I/O callback lifecycle events, *not inferred states*, to this local event contract. See `docs/VOICE_IO_HOOK.md`.
