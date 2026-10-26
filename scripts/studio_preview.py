#!/usr/bin/env python3
"""Preview policy matching WITHOUT applying lights or opening a network socket."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rgd_visual.studio import load_profile, preview  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="OpenRGD Visual Effects Studio — dry-run scene preview")
    parser.add_argument("--profile", type=Path, default=ROOT / "profiles/paky01-studio.preview.json")
    parser.add_argument("--source", default="voice")
    parser.add_argument("--event", default="playback.started")
    args = parser.parse_args()
    profile = load_profile(args.profile)
    print(json.dumps(preview(profile, args.source, args.event), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
