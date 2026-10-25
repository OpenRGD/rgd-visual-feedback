"""Hardware adapter; never touches robot actuator/somatic interfaces."""
from __future__ import annotations
import asyncio
import logging
from typing import Protocol

from .config import Settings, VisualState
from .protocol import SERVICE_UUID, WRITE_UUID, brightness_packet, color_packet

LOG = logging.getLogger(__name__)


class VisualOutput(Protocol):
    """Backend-independent desired-state interface."""
    def set_state(self, name: str) -> dict: ...
    def status(self) -> dict: ...


class MiraclesStarBLE:
    def __init__(self, config: Settings):
        self.config = config
        self.desired = "idle"
        self.applied: str | None = None
        self.connected = False
        self.last_error: str | None = None
        self.revision = 0
        self.changed = asyncio.Event()

    def set_state(self, name: str) -> dict:
        if name not in self.config.states:
            raise ValueError("Unknown state")
        if self.desired != name:
            self.desired = name
            self.revision += 1
            self.changed.set()
        return {"accepted": True, "desired": self.desired, "connected": self.connected}

    def status(self) -> dict:
        return {
            "adapter": "miracles-star-ble",
            "address": self.config.device_address,
            "connected": self.connected,
            "desired": self.desired,
            "applied": self.applied,
            "last_error": self.last_error,
        }

    @staticmethod
    async def _apply(client, state: VisualState) -> None:
        # Set brightness first, as verified in the interactive RGB test.
        await client.write_gatt_char(WRITE_UUID, brightness_packet(state.brightness), response=True)
        if state.brightness > 0:
            await client.write_gatt_char(WRITE_UUID, color_packet(state.color), response=True)

    async def run(self) -> None:
        """One BLE owner, persistent reconnect with desired-state replay."""
        # Import lazily: pure packet tests do not require a BLE adapter.
        from bleak import BleakScanner, BleakClient

        while True:
            self.connected = False
            self.applied = None
            try:
                LOG.info("Looking for BLE ring %s", self.config.device_address)
                device = await BleakScanner.find_device_by_address(
                    self.config.device_address, timeout=15
                )
                if device is None:
                    raise ConnectionError("BLE device not discovered")
                async with BleakClient(device, timeout=20) as client:
                    if client.services.get_service(SERVICE_UUID) is None:
                        raise ConnectionError("Expected FFF0 GATT service not found")
                    char = client.services.get_characteristic(WRITE_UUID)
                    if char is None or "write" not in char.properties:
                        raise ConnectionError("Expected writable FFF3 not found")
                    self.connected = True
                    self.last_error = None
                    LOG.info("RGB connected to %s", self.config.device_address)
                    sent_revision = -1
                    while client.is_connected:
                        # clear BEFORE reading desired revision to avoid missing updates
                        self.changed.clear()
                        rev = self.revision
                        name = self.desired
                        if rev != sent_revision:
                            await self._apply(client, self.config.states[name])
                            self.applied = name
                            sent_revision = rev
                            LOG.info("LED state applied: %s", name)
                        try:
                            await asyncio.wait_for(self.changed.wait(), timeout=2)
                        except asyncio.TimeoutError:
                            pass
                    raise ConnectionError("BLE link disconnected")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = str(exc)[:300]
                LOG.warning("RGB temporarily unavailable: %s", self.last_error)
            finally:
                self.connected = False
                self.applied = None
            await asyncio.sleep(3)
