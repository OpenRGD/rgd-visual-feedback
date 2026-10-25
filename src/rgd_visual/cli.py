"""paky-led speaking/listening/thinking/error/idle/off/status"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from .config import REQUIRED_STATES
from .server import socket_path


async def request(command: str) -> dict:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(socket_path())), timeout=2)
    except (ConnectionRefusedError, FileNotFoundError, OSError, asyncio.TimeoutError) as exc:
        raise RuntimeError("LED service unavailable (check: systemctl --user status paky01-visual-feedback)") from exc
    try:
        body = {"version": 1, "command": "status"}
        if command != "status":
            body = {"version": 1, "command": "set_state", "state": command}
        writer.write((json.dumps(body) + "\n").encode())
        await writer.drain()
        answer = await asyncio.wait_for(reader.readline(), timeout=3)
        if not answer:
            raise RuntimeError("Empty response from LED service")
        return json.loads(answer)
    finally:
        writer.close()
        await writer.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="Paky-01 LED visual state")
    parser.add_argument("state", choices=(*REQUIRED_STATES, "status"))
    args = parser.parse_args()
    try:
        result = asyncio.run(request(args.state))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise SystemExit(2)
    except (RuntimeError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()
