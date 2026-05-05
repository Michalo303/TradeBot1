from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


def validate_manifest(data: dict) -> dict:
    if not data.get("variant"):
        raise ValueError("manifest must have a non-empty 'variant' field")
    if not data.get("pairs"):
        raise ValueError("manifest must have a non-empty 'pairs' list")
    return data


def _parse_timerange_days(timerange: str) -> int:
    start_str, end_str = timerange.split("-")
    start = date(int(start_str[:4]), int(start_str[4:6]), int(start_str[6:8]))
    end = date(int(end_str[:4]), int(end_str[4:6]), int(end_str[6:8]))
    return (end - start).days


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Freqtrade backtest matrix.")
    parser.add_argument("manifest", nargs="?", type=Path, help="Matrix manifest JSON")
    parser.add_argument("--timerange", action="append", dest="timeranges", default=[])
    parser.add_argument("--max-pairs", type=int, default=5)
    parser.add_argument("--max-timerange-days", type=int, default=365)
    parser.add_argument("--print-commands", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    if args.max_pairs <= 0:
        print("ERROR: --max-pairs must be > 0", file=sys.stderr)
        raise SystemExit(1)

    if args.max_timerange_days <= 0:
        print("ERROR: --max-timerange-days must be > 0", file=sys.stderr)
        raise SystemExit(1)

    for tr in args.timeranges:
        days = _parse_timerange_days(tr)
        if days > args.max_timerange_days:
            print(
                f"ERROR: timerange {tr} spans {days} days, exceeds --max-timerange-days {args.max_timerange_days}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    if args.manifest is None:
        if not args.timeranges:
            print("ERROR: provide a manifest and at least one --timerange", file=sys.stderr)
            raise SystemExit(1)
        return

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest = validate_manifest(data)

    if len(manifest["pairs"]) > args.max_pairs:
        print(
            f"ERROR: manifest has {len(manifest['pairs'])} pairs, exceeds --max-pairs {args.max_pairs}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    cells = [(manifest["variant"], tr) for tr in args.timeranges]
    n = len(cells)

    if not args.confirm and not args.print_commands:
        print(f"Run plan: {n} cell(s) — variant={manifest['variant']}, timeranges={args.timeranges}")
        print("Pass --confirm to execute, or --print-commands to preview docker commands.")
        raise SystemExit(0)


if __name__ == "__main__":
    main()
