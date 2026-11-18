#!/usr/bin/env python3
"""OpenRGD eye composition — synthetic OFFLINE policy preview, never hardware."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rgd_visual.eye_composition import compose_preview  # noqa: E402
from rgd_visual.expression_packs import load_pack  # noqa: E402


def read_bounded(path: Path, *, limit: int = 16 * 1024) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Invalid, symlinked or oversized synthetic input")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Composition input must be a JSON object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenRGD generic eyes — composition preview ONLY")
    parser.add_argument("--pack", type=Path, default=ROOT / "packs/eyes/core-v0.1.json")
    parser.add_argument("--input", type=Path,
                        default=ROOT / "examples/expressions/eye-composition-speaking-friendly.synthetic.json")
    args = parser.parse_args()
    result = compose_preview(load_pack(args.pack), read_bounded(args.input))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
