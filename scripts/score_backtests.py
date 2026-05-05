from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BacktestMetrics:
    source: str
    strategy: str
    trades: int
    profit_factor: float
    profit_total_pct: float
    max_drawdown_pct: float
    winrate: float
    avg_duration_seconds: int
    winning_days: int
    draw_days: int
    losing_days: int
    backtest_days: int


def confidence_label(trades: int, incomplete: bool) -> str:
    if incomplete or trades < 30:
        return "LOW"
    if trades < 100:
        return "MEDIUM"
    return "HIGH"


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def parse_backtest_payload(payload: dict[str, Any], source: str) -> BacktestMetrics:
    strategy_name = payload["strategy_comparison"][0]["key"]
    data = payload["strategy"][strategy_name]
    return BacktestMetrics(
        source=source,
        strategy=strategy_name,
        trades=_int(data.get("total_trades")),
        profit_factor=_float(data.get("profit_factor")),
        profit_total_pct=_float(data.get("profit_total_pct")),
        max_drawdown_pct=_float(data.get("max_drawdown_account")),
        winrate=_float(data.get("winrate")),
        avg_duration_seconds=_int(data.get("holding_avg_s")),
        winning_days=_int(data.get("winning_days")),
        draw_days=_int(data.get("draw_days")),
        losing_days=_int(data.get("losing_days")),
        backtest_days=_int(data.get("backtest_days")),
    )
