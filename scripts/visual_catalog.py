#!/usr/bin/env python3
"""OpenRGD Visual Studio local catalog CLI — no daemon, BLE or screen access.

WARNING: --confirm phrases protect against accidental local CLI actions;
they are NOT cryptographic authentication or safety authorization.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rgd_visual.catalog import CatalogStore, DEFAULT_ROOT  # noqa: E402


def _input_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024:
        raise ValueError("Candidate input missing, symlinked or too large")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Candidate input must be a JSON object")
    return raw


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Visual Studio: versioned, operator-reviewed LOCAL expression catalog"
    )
    parser.add_argument("--robot", required=True, help="robot instance (e.g. paky-02)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="Private local data root (not the live LED configuration)")
    commands = parser.add_subparsers(dest="command", required=True)
    queue = commands.add_parser("queue", help="Import an operator expression or full cognitive proposal")
    queue.add_argument("--file", type=Path, required=True)
    commands.add_parser("pending", help="List queued / approved / rejected proposals (read-only)")
    commands.add_parser("list", help="List latest approved catalog revisions (read-only)")
    show = commands.add_parser("show", help="Display approved latest revision (read-only)")
    show.add_argument("--expression", required=True)
    hist = commands.add_parser("history", help="Display immutable-by-protocol revision history")
    hist.add_argument("--expression", required=True)
    approve = commands.add_parser("approve", help="Explicitly create new approved catalog revision")
    approve.add_argument("--proposal", required=True)
    approve.add_argument("--expected-revision", required=True, type=int)
    approve.add_argument("--confirm", required=True, help='Exact "APPROVE <robot> <proposal>"')
    reject = commands.add_parser("reject", help="Reject queued proposal without deleting evidence")
    reject.add_argument("--proposal", required=True)
    reject.add_argument("--reason", required=True)
    reject.add_argument("--confirm", required=True, help='Exact "REJECT <robot> <proposal>"')
    rollback = commands.add_parser("rollback", help="Append a new revision using a previously approved recipe")
    rollback.add_argument("--expression", required=True)
    rollback.add_argument("--to-revision", type=int, required=True)
    rollback.add_argument("--expected-revision", type=int, required=True)
    rollback.add_argument("--confirm", required=True,
                          help='Exact "ROLLBACK <robot> <expression> TO <revision>"')
    args = parser.parse_args(argv)
    store = CatalogStore(args.root, args.robot)

    try:
        if args.command == "queue":
            result = store.queue(_input_json(args.file))
        elif args.command == "pending":
            result = store.list_proposals()
        elif args.command == "list":
            result = store.list_catalog()
        elif args.command == "show":
            result = store.show(args.expression)
        elif args.command == "history":
            result = store.history(args.expression)
        elif args.command == "approve":
            result = store.approve(args.proposal, expected_revision=args.expected_revision,
                                   confirmation=args.confirm)
        elif args.command == "reject":
            result = store.reject(args.proposal, reason=args.reason, confirmation=args.confirm)
        else:
            result = store.rollback(args.expression, to_revision=args.to_revision,
                                    expected_revision=args.expected_revision,
                                    confirmation=args.confirm)
    except (ValueError, PermissionError, OSError, json.JSONDecodeError) as exc:
        # Never produce false "success" receipts or fall back to hardware.
        print("CATALOG ERROR: " + str(exc), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
