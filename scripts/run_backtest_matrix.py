from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scripts.score_backtests import BacktestScore, load_and_score


FREQTRADE_IMAGE = "freqtradeorg/freqtrade:2024.5"
CONTAINER_DATA_DIR = "/freqtrade/user_data"
HOST_RESULTS_DIR = Path("user_data/backtest_results")


def build_docker_cmd(
    manifest: dict,
    timerange: str,
    run_id: str,
    configs: list[Path],
) -> tuple[list[str], Path]:
    variant = manifest["variant"]
    pairs = manifest["pairs"]
    filename = f"nfix7-{variant}-{timerange}-{run_id}.json"
    output_path = HOST_RESULTS_DIR / filename
    container_output = f"{CONTAINER_DATA_DIR}/backtest_results/{filename}"

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{Path.cwd()}:/freqtrade",
        FREQTRADE_IMAGE,
        "backtesting",
    ]
    for cfg in configs:
        cmd += ["--config", f"{CONTAINER_DATA_DIR}/config/{cfg.name}"]
    cmd += [
        "--strategy", "NostalgiaForInfinityX7",
        "--timerange", timerange,
        "--pairs", *pairs,
        "--export", "trades",
        "--export-filename", container_output,
    ]
    return cmd, output_path


@dataclass(frozen=True)
class CellResult:
    variant: str
    timerange: str
    score: BacktestScore


def score_cell(output_path: Path) -> BacktestScore:
    try:
        return load_and_score(output_path)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        print(f"ERROR: failed to parse {output_path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def render_matrix_summary(cells: list[CellResult]) -> str:
    lines = [
        "# TradeBot1 Backtest Matrix Summary",
        "",
        "This report is not a live trading recommendation.",
        "portfolio behavior not replicated: results are per-variant directional comparison only.",
        "",
        "| Variant | Timerange | Trades | Score | Confidence | Recommendation |",
        "|---|---|---:|---:|---|---|",
    ]
    for cell in cells:
        s = cell.score
        m = s.metrics
        lines.append(
            f"| {cell.variant} | {cell.timerange} | {m.trades} | {s.score} | {s.confidence} | {s.recommendation} |"
        )
    return "\n".join(lines) + "\n"


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
