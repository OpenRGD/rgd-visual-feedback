#!/usr/bin/env python3
"""Export a robot-specific Visual Studio preview from a generic pack (offline)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rgd_visual.expression_packs import load_pack, preview_profile  # noqa: E402
from rgd_visual.studio import preview  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic OpenRGD eye pack -> offline Studio preview")
    parser.add_argument("--pack", type=Path, default=ROOT / "packs/eyes/core-v0.1.json")
    parser.add_argument("--robot-id", required=True, help="Explicit preview identity, not a device connection")
    parser.add_argument("--without-ring", action="store_true", help="Create an eyes-only preview")
    parser.add_argument("--source", default=None, help="Optional source for preview() test")
    parser.add_argument("--event", default=None, help="Optional event for preview() test")
    args = parser.parse_args()
    if (args.source is None) != (args.event is None):
        parser.error("--source and --event must be supplied together")
    profile = preview_profile(load_pack(args.pack), args.robot_id, include_ring=not args.without_ring)
    result = preview(profile, args.source, args.event) if args.source is not None else profile
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
