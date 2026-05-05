from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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


@dataclass(frozen=True)
class BacktestScore:
    metrics: BacktestMetrics
    score: int
    confidence: str
    recommendation: str
    reasons: tuple[str, ...]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> int:
    return int(round(max(minimum, min(maximum, value))))


def score_backtest(metrics: BacktestMetrics, incomplete: bool = False) -> BacktestScore:
    score = 50.0
    reasons: list[str] = []

    if metrics.profit_factor >= 1.5:
        score += 15
    elif metrics.profit_factor >= 1.2:
        score += 8
    elif metrics.profit_factor > 0:
        score -= 10

    if metrics.max_drawdown_pct >= 20:
        score -= 30
        reasons.append("max drawdown is above 20%")
    elif metrics.max_drawdown_pct >= 15:
        score -= 20
        reasons.append("max drawdown is above live checklist threshold")
    elif metrics.max_drawdown_pct >= 10:
        score -= 10

    if metrics.trades < 30:
        score -= 25
        reasons.append("fewer than 30 closed trades")
    elif metrics.trades >= 100:
        score += 10

    if metrics.winrate >= 0.6:
        score += 8
    elif metrics.winrate < 0.5 and metrics.trades > 0:
        score -= 8

    hours = metrics.avg_duration_seconds / 3600 if metrics.avg_duration_seconds else 0
    if hours > 48:
        score -= 10
        reasons.append("average trade duration is above 48h")
    elif 0 < hours <= 24:
        score += 5

    active_days = metrics.winning_days + metrics.draw_days + metrics.losing_days
    if active_days >= 5 and metrics.winning_days / active_days >= 0.65:
        score += 7
    elif active_days >= 5 and metrics.losing_days / active_days >= 0.45:
        score -= 10

    confidence = confidence_label(metrics.trades, incomplete=incomplete)
    final_score = _clamp(score)

    if confidence == "LOW":
        recommendation = "COLLECT_MORE_DATA"
    elif final_score >= 75 and metrics.max_drawdown_pct < 15:
        recommendation = "KEEP_CURRENT"
    elif final_score >= 65 and metrics.trades < 60:
        recommendation = "EXPAND_PAIRLIST"
    elif metrics.max_drawdown_pct >= 15:
        recommendation = "TIGHTEN_PAIRLIST"
    else:
        recommendation = "DO_NOT_CHANGE_YET"

    return BacktestScore(
        metrics=metrics,
        score=final_score,
        confidence=confidence,
        recommendation=recommendation,
        reasons=tuple(reasons),
    )


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


def render_markdown_report(scores: list[BacktestScore]) -> str:
    lines = [
        "# TradeBot1 Risk Score Report",
        "",
        "This report is not a live trading recommendation.",
        "",
        "| Source | Trades | Profit Factor | Drawdown % | Win Rate % | Score | Confidence | Recommendation |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for item in scores:
        m = item.metrics
        lines.append(
            f"| {m.source} | {m.trades} | {m.profit_factor:.2f} | "
            f"{m.max_drawdown_pct:.2f} | {m.winrate * 100:.1f} | "
            f"{item.score} | {item.confidence} | {item.recommendation} |"
        )
    lines.extend(["", "## Notes", ""])
    for item in scores:
        if item.reasons:
            lines.append(f"- `{item.metrics.source}`: " + "; ".join(item.reasons))
    if all(not item.reasons for item in scores):
        lines.append("- No additional scoring penalties were recorded.")
    return "\n".join(lines) + "\n"


def score_to_dict(item: BacktestScore) -> dict[str, object]:
    m = item.metrics
    return {
        "source": m.source,
        "strategy": m.strategy,
        "trades": m.trades,
        "profit_factor": m.profit_factor,
        "profit_total_pct": m.profit_total_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
        "winrate": m.winrate,
        "score": item.score,
        "confidence": item.confidence,
        "recommendation": item.recommendation,
        "reasons": list(item.reasons),
    }


def load_and_score(path: Path) -> BacktestScore:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return score_backtest(parse_backtest_payload(payload, source=path.name))


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Freqtrade backtest JSON files.")
    parser.add_argument("backtests", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()

    scores = [load_and_score(path) for path in args.backtests]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = args.output_dir / f"risk-score-{stamp}.json"
    md_path = args.output_dir / f"risk-score-{stamp}.md"
    json_path.write_text(
        json.dumps([score_to_dict(item) for item in scores], indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown_report(scores), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
