#!/usr/bin/env python3
"""Render-plan inspection for Visual Studio. PREVIEW ONLY / NO DEVICES."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rgd_visual.expressions import (  # noqa: E402
    plan_cognitive_proposal, plan_eye_preview, read_preview,
)


def main():
    parser = argparse.ArgumentParser(description="OpenRGD Expressive Eyes — OFFLINE preview")
    parser.add_argument("--expression", type=Path,
                        default=ROOT / "examples/expressions/meraviglia_curiosa.preview.json")
    parser.add_argument("--proposal", type=Path, help="Opt-in synthetic Cognitive proposal fixture")
    args = parser.parse_args()
    if args.proposal:
        source = args.proposal
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 16 * 1024:
            raise SystemExit("Invalid proposal file")
        result = plan_cognitive_proposal(json.loads(source.read_text(encoding="utf-8")))
    else:
        result = plan_eye_preview(read_preview(args.expression))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
