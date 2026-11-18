# OpenRGD Visual Feedback

Hardware-agnostic visual feedback for embodied robotic systems.

## Version 0.2.0

First operational adapter:
- Miracles.Star BLE RGB-IC
- Persistent Bluetooth connection
- Automatic reconnection
- Unix socket IPC
- Configurable visual states
- CLI and systemd user service

## Architecture

OpenRGD Events
  -> Visual Feedback
  -> Hardware Adapter
  -> Physical Output

## Supported states

- idle
- listening
- thinking
- speaking
- error
- off

## First implementation

Paky-01 humanoid robot.

Physically tested on Ubuntu 22.04.

## Documentation

See README_IT.md and docs/VOICE_IO_HOOK.md.

## Safety

Visual feedback is independent from actuator control
and the deterministic Somatic Runtime.

## Reusable eye-expression pack (candidate)

- [Core Eye Expressions v0.1](docs/SHARED_EYE_EXPRESSIONS.md): 21 robot-neutral eye recipes in Visual Feedback, plus an offline generator for any robot ID. All outputs are preview-only. Visual Effects Studio in `rgd-console` is a UI consumer, not a duplicate engine.
