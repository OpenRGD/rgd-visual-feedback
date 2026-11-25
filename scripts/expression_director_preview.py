#!/usr/bin/env python3
"""Offline director timeline runner. No live input or automatic scheduling."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rgd_visual.expression_director import ExpressionDirector  # noqa: E402
from rgd_visual.expression_packs import load_pack  # noqa: E402

MAX_BYTES = 256 * 1024
MAX_STEPS = 128


def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate JSON key")
        out[key] = value
    return out


def load_timeline(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Timeline must be a regular file")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Empty or oversized timeline")
    frames = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_STEPS:
        raise ValueError("Expected 1..128 synthetic steps")
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=ROOT / "examples/expressions/expression-director.synthetic.json")
    parser.add_argument("--pack", type=Path, default=ROOT / "packs/eyes/core-v0.1.json")
    parser.add_argument("--frame-index", type=int, help="Export only the selected nested composer result (zero-based)")
    args = parser.parse_args()
    try:
        frames = load_timeline(args.input)
        first = frames[0]
        director = ExpressionDirector(load_pack(args.pack), robot_id=first["composition"]["robot_id"],
                                      session_id=first["session_id"])
        results = [director.step(frame) for frame in frames]
        if args.frame_index is not None:
            if not 0 <= args.frame_index < len(results):
                raise ValueError("Frame index out of range")
            output = results[args.frame_index]["composition"]
        else:
            output = results
    except (OSError, ValueError, TypeError, KeyError, RecursionError, IndexError):
        print("Invalid synthetic timeline; no output emitted", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
