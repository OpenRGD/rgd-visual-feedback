import asyncio
import os
from pathlib import Path
import tempfile
import unittest

from rgd_visual.cli import request
from rgd_visual.config import load
from rgd_visual.driver import MiraclesStarBLE
from rgd_visual.server import handle
from rgd_visual.protocol import brightness_packet, color_packet

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self):
        self.writes = []

    async def write_gatt_char(self, uuid, payload, response=False):
        self.writes.append((uuid, bytes(payload), response))


class IPCTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_cli_accepts_state_and_reports_status(self):
        with tempfile.TemporaryDirectory(prefix="rgd-visual-test-") as tmp:
            old_runtime = os.environ.get("XDG_RUNTIME_DIR")
            os.environ["XDG_RUNTIME_DIR"] = tmp
            try:
                path = Path(tmp) / "paky01-visual-feedback.sock"
                adapter = MiraclesStarBLE(load(ROOT / "config.example.json"))
                server = await asyncio.start_unix_server(
                    lambda r, w: handle(r, w, adapter), path=str(path)
                )
                try:
                    result = await request("listening")
                    self.assertEqual(result["desired"], "listening")
                    self.assertTrue(result["accepted"])
                    status = await request("status")
                    self.assertTrue(status["ok"])
                    self.assertEqual(status["desired"], "listening")
                    self.assertFalse(status["connected"])
                finally:
                    server.close()
                    await server.wait_closed()
            finally:
                if old_runtime is None:
                    del os.environ["XDG_RUNTIME_DIR"]
                else:
                    os.environ["XDG_RUNTIME_DIR"] = old_runtime

    async def test_ble_packet_sequence(self):
        client = FakeClient()
        adapter = MiraclesStarBLE(load(ROOT / "config.example.json"))
        spec = adapter.config.states["speaking"]
        await adapter._apply(client, spec)
        self.assertEqual([v[1] for v in client.writes], [
            brightness_packet(35), color_packet("#00FF46")
        ])
        self.assertTrue(all(write[2] for write in client.writes))

    async def test_off_only_changes_brightness(self):
        client = FakeClient()
        adapter = MiraclesStarBLE(load(ROOT / "config.example.json"))
        await adapter._apply(client, adapter.config.states["off"])
        self.assertEqual([v[1] for v in client.writes], [brightness_packet(0)])

if __name__ == "__main__":
    unittest.main()
