#!/usr/bin/env python3
"""Explicit synthetic voice lifecycle smoke test.

Default is DRY RUN and does not connect to any service.
Use --apply only after intentionally deploying the v0.3 Visual daemon.
No audio, BLE pairing, actuator, CAN or Somatic control.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import uuid

SCHEMA = "openrgd.visual.voice-event.v0.1-candidate"
EVENTS = (
    "listening.started",
    "inference.started",
    "playback.started",
    "playback.ended",
    "voice.ready",
)


def socket_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "paky01-visual-feedback.sock"


async def send(message: dict) -> dict:
    reader, writer = await asyncio.wait_for(
        asyncio.open_unix_connection(str(socket_path())), timeout=2
    )
    try:
        writer.write((json.dumps(message) + "\n").encode("utf-8"))
        await asyncio.wait_for(writer.drain(), timeout=2)
        reply = await asyncio.wait_for(reader.readline(), timeout=3)
        if not reply:
            raise RuntimeError("Empty Visual Feedback service response")
        response = json.loads(reply)
        if not response.get("ok") or not response.get("accepted"):
            raise RuntimeError(f"Event not accepted by Visual service: {response}")
        return response
    finally:
        writer.close()
        await writer.wait_closed()


async def main(apply: bool) -> None:
    session = uuid.uuid4().hex
    print("SYNTHETIC ONLY: This is NOT Voice Studio live playback evidence.")
    print(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
    for seq, name in enumerate(EVENTS):
        message = {
            "version": 1,
            "command": "voice_event",
            "schema_version": SCHEMA,
            "source": "rgd-voice",
            "session_id": session,
            "sequence": seq,
            "event": name,
        }
        print(json.dumps(message))
        if apply:
            print("  response:", json.dumps(await send(message)))
            await asyncio.sleep(1.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually send events to local Visual daemon")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.apply))
