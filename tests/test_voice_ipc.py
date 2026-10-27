"""Socket integration tests. No physical BLE connection is created."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from rgd_visual.server import handle
from rgd_visual.voice_events import VoiceEventGate, SCHEMA


class DummyAdapter:
    def __init__(self):
        self.desired = "idle"
        self.connected = False
        self.calls = []

    def status(self):
        return {"desired": self.desired, "connected": self.connected, "applied": None}

    def set_state(self, name):
        self.desired = name
        self.calls.append(name)
        return {"accepted": True, "desired": name, "connected": False}


def event(name, seq):
    return {
        "version": 1, "command": "voice_event",
        "schema_version": SCHEMA, "source": "rgd-voice",
        "session_id": "1" * 32, "sequence": seq, "event": name,
    }


class IPCVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_socket_retains_legacy_cli_and_routes_events(self):
        with tempfile.TemporaryDirectory() as temp:
            socket = Path(temp) / "test-visual.sock"
            adapter, gate = DummyAdapter(), VoiceEventGate()
            server = await asyncio.start_unix_server(
                lambda r, w: handle(r, w, adapter, gate), path=str(socket)
            )

            async def query(payload):
                reader, writer = await asyncio.open_unix_connection(str(socket))
                try:
                    writer.write((json.dumps(payload) + "\n").encode())
                    await writer.drain()
                    return json.loads(await asyncio.wait_for(reader.readline(), timeout=2))
                finally:
                    writer.close()
                    await writer.wait_closed()

            try:
                first = await query(event("listening.started", 0))
                self.assertTrue(first["ok"])
                self.assertTrue(first["accepted"])
                self.assertEqual(first["desired"], "listening")

                second = await query(event("playback.started", 1))
                self.assertEqual(second["desired"], "speaking")

                stale = await query(event("playback.ended", 0))
                self.assertTrue(stale["ok"])
                self.assertFalse(stale["accepted"])
                self.assertEqual(adapter.desired, "speaking")

                invalid = await query(event("model.text.generated", 2))
                self.assertFalse(invalid["ok"])
                self.assertEqual(adapter.desired, "speaking")

                status = await query({"version": 1, "command": "status"})
                self.assertTrue(status["ok"])
                self.assertEqual(status["voice_event"]["last_sequence"], 1)
                self.assertEqual(status["voice_event"]["last_event"], "playback.started")
                self.assertFalse(status["voice_event"]["physical_event_verified"])
                self.assertIsNone(status["applied"])

                manual = await query({"version": 1, "command": "set_state", "state": "error"})
                self.assertTrue(manual["ok"])
                self.assertEqual(manual["desired"], "error")
            finally:
                server.close()
                await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
