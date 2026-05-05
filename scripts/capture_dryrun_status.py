"""Capture daily dry-run status snapshot via Freqtrade REST API."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_URL = "http://localhost:8080"
DEFAULT_USER = "freqtrader"
DEFAULT_PASS = "Freqtrade2026!"
SNAPSHOTS_DIR = Path("logs/dryrun-snapshots")


def _auth_header(user: str, password: str) -> str:
    token = b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _get(url: str, path: str, auth: str) -> dict:
    req = urllib.request.Request(
        f"{url}{path}",
        headers={"Authorization": auth},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def capture(url: str, user: str, password: str) -> dict:
    auth = _auth_header(user, password)
    profit = _get(url, "/api/v1/profit", auth)
    trades = _get(url, "/api/v1/trades?limit=50", auth)
    whitelist = _get(url, "/api/v1/whitelist", auth)
    status = _get(url, "/api/v1/status", auth)

    open_trades = [t for t in trades.get("trades", []) if t.get("is_open")]
    closed_trades = [t for t in trades.get("trades", []) if not t.get("is_open")]

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "bot_start_date": profit.get("bot_start_date"),
        "closed_trade_count": profit.get("closed_trade_count", 0),
        "open_trade_count": len(open_trades),
        "total_trades": profit.get("trade_count", 0),
        "profit_closed_pct": profit.get("profit_closed_percent", 0.0),
        "profit_all_pct": profit.get("profit_all_percent", 0.0),
        "winning_trades": profit.get("winning_trades", 0),
        "losing_trades": profit.get("losing_trades", 0),
        "profit_factor": profit.get("profit_factor"),
        "max_drawdown_pct": profit.get("max_drawdown", 0.0),
        "avg_duration": profit.get("avg_duration"),
        "whitelist_count": whitelist.get("length", 0),
        "whitelist": whitelist.get("whitelist", []),
        "open_trades": [
            {"pair": t["pair"], "profit_pct": t.get("profit_pct"), "open_date": t.get("open_date")}
            for t in open_trades
        ],
        "note": "not a live trading recommendation",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture Freqtrade dry-run status snapshot.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASS)
    parser.add_argument("--output-dir", type=Path, default=SNAPSHOTS_DIR)
    args = parser.parse_args()

    try:
        snapshot = capture(args.url, args.user, args.password)
    except urllib.error.URLError as exc:
        print(f"ERROR: cannot reach Freqtrade API at {args.url}: {exc}", file=sys.stderr)
        print("Run via SSH tunnel: ssh -L 8080:localhost:8080 root@91.99.99.158", file=sys.stderr)
        raise SystemExit(1) from exc

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = args.output_dir / f"dryrun-{stamp}.json"
    out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    print(f"  closed trades: {snapshot['closed_trade_count']}")
    print(f"  open trades:   {snapshot['open_trade_count']}")
    print(f"  profit (closed): {snapshot['profit_closed_pct']:.4f}%")
    print(f"  whitelist: {snapshot['whitelist_count']} pairs")


if __name__ == "__main__":
    main()
