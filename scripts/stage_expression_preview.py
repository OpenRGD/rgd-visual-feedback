#!/usr/bin/env python3
"""Generate a Visual Studio scene candidate from data. NO physical effects.

Reads bounded JSON inputs and prints the staged profile JSON to stdout.
Does NOT persist, connect to an audio/BLE/display device or contact cognition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rgd_visual.studio import load_profile, stage_expression_preview  # noqa: E402


def read_bounded_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024:
        raise ValueError("Expression/proposal JSON is missing or beyond 16 KiB")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expression/proposal must be an object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Visual Studio v0.2B — offline declarative staging")
    parser.add_argument("--profile", type=Path, default=ROOT / "profiles/paky02-expressive-studio.preview.json")
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--proposal", type=Path, help="Complete Cognitive proposal wrapper (synthetic)")
    candidate.add_argument("--expression", type=Path, help="Operator-authored standalone expression")
    parser.add_argument("--scene", default="welcome")
    parser.add_argument("--zone", default="expressive-eyes")
    parser.add_argument("--replace-existing", action="store_true", help="Explicit draft-only catalog replacement")
    args = parser.parse_args()
    source = args.proposal or args.expression
    result = stage_expression_preview(
        load_profile(args.profile),
        read_bounded_json(source),
        args.scene,
        zone_id=args.zone,
        replace_existing=args.replace_existing,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("CANDIDATE ONLY: no file/device was modified.", file=sys.stderr)


if __name__ == "__main__":
    main()
