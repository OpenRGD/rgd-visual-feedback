"""User-local Unix socket endpoint for robot events; no network exposure."""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import signal

from .config import DEFAULT_CONFIG, load
from .driver import MiraclesStarBLE
from .voice_events import VoiceEventGate

LOG = logging.getLogger(__name__)


def socket_path() -> Path:
    runtime = os.getenv("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return Path(runtime) / "paky01-visual-feedback.sock"


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, adapter: MiraclesStarBLE, voice_gate: VoiceEventGate | None = None):
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=5)
        if len(raw) > 1024:
            raise ValueError("Request too large")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Expected JSON object with version=1")
        command = data.get("command")
        if command == "status":
            result = adapter.status()
            if voice_gate is not None:
                result["voice_event"] = voice_gate.status()
        elif command == "voice_event":
            if voice_gate is None:
                raise ValueError("Voice event integration unavailable")
            result = voice_gate.consume(data, adapter)
        elif command == "set_state":
            state = data.get("state")
            if not isinstance(state, str):
                raise ValueError("Missing state")
            result = adapter.set_state(state)
        else:
            raise ValueError("Unknown command")
        response = {"ok": True, **result}
    except (ValueError, json.JSONDecodeError, asyncio.TimeoutError) as exc:
        response = {"ok": False, "error": str(exc)}
    except Exception:
        LOG.exception("Unexpected IPC error")
        response = {"ok": False, "error": "internal error"}
    try:
        writer.write((json.dumps(response) + "\n").encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def clear_stale_socket(path: Path) -> None:
    if not path.exists():
        return
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(path)), timeout=2)
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        path.unlink(missing_ok=True)
    else:
        writer.close()
        await writer.wait_closed()
        raise RuntimeError(f"Visual service already active at {path}")


async def serve(config_path: Path) -> None:
    cfg = load(config_path)
    path = socket_path()
    if not path.parent.is_dir():
        raise RuntimeError(f"Runtime dir missing: {path.parent}")
    await clear_stale_socket(path)
    adapter = MiraclesStarBLE(cfg)
    voice_gate = VoiceEventGate()
    old_umask = os.umask(0o177)
    try:
        server = await asyncio.start_unix_server(
            lambda r, w: handle(r, w, adapter, voice_gate), path=str(path), limit=2048
        )
    finally:
        os.umask(old_umask)
    path.chmod(0o600)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    worker = asyncio.create_task(adapter.run(), name="rgb-ble-reconnect")
    LOG.info("Local socket ready: %s", path)
    try:
        await stop.wait()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        server.close()
        await server.wait_closed()
        path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paky-01 visual feedback daemon")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(serve(args.config))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
