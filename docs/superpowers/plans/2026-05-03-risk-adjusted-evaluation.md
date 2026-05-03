# Risk-Adjusted Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small, auditable reporting layer that scores Freqtrade backtest JSON files by risk-adjusted quality instead of raw profit.

**Architecture:** Keep strategy logic untouched. Add a pure-Python scoring module that parses Freqtrade backtest output, computes score/confidence/recommendation, and writes Markdown/JSON reports. Add stdlib tests so CI can verify scoring behavior without Docker or market data.

**Tech Stack:** Python 3.12 standard library, `unittest`, existing GitHub Actions workflow.

---

## File Structure

- Create `scripts/score_backtests.py`: CLI and scoring implementation. Owns parsing Freqtrade JSON, scoring, confidence labels, recommendations, and report rendering.
- Create `tests/test_score_backtests.py`: stdlib `unittest` coverage for parsing, low-sample confidence, scoring penalties, and recommendations.
- Create `reports/README.md`: explains generated risk reports and what is safe to commit.
- Modify `.github/workflows/repo-safety.yml`: run tests after safety checks.
- Modify `README.md`: document the score command.

## Task 1: Scoring Module Skeleton

**Files:**
- Create: `scripts/score_backtests.py`
- Test: `tests/test_score_backtests.py`

- [ ] **Step 1: Write the failing import and confidence test**

Create `tests/test_score_backtests.py` with:

```python
import unittest

from scripts.score_backtests import confidence_label


class ScoreBacktestsTests(unittest.TestCase):
    def test_confidence_label_uses_trade_count_thresholds(self):
        self.assertEqual(confidence_label(0, incomplete=False), "LOW")
        self.assertEqual(confidence_label(29, incomplete=False), "LOW")
        self.assertEqual(confidence_label(30, incomplete=False), "MEDIUM")
        self.assertEqual(confidence_label(99, incomplete=False), "MEDIUM")
        self.assertEqual(confidence_label(100, incomplete=False), "HIGH")
        self.assertEqual(confidence_label(100, incomplete=True), "LOW")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.score_backtests'`.

- [ ] **Step 3: Write minimal implementation**

Create `scripts/score_backtests.py` with:

```python
from __future__ import annotations


def confidence_label(trades: int, incomplete: bool) -> str:
    if incomplete or trades < 30:
        return "LOW"
    if trades < 100:
        return "MEDIUM"
    return "HIGH"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: PASS, 1 test.

- [ ] **Step 5: Commit**

```bash
git add scripts/score_backtests.py tests/test_score_backtests.py
git commit -m "test: add risk score confidence thresholds"
```

## Task 2: Parse Freqtrade Backtest JSON

**Files:**
- Modify: `scripts/score_backtests.py`
- Modify: `tests/test_score_backtests.py`

- [ ] **Step 1: Add failing parser test**

Append inside `ScoreBacktestsTests`:

```python
    def test_parse_backtest_extracts_strategy_metrics(self):
        payload = {
            "strategy": {
                "NostalgiaForInfinityX7": {
                    "total_trades": 2,
                    "profit_factor": 1.8,
                    "profit_total_pct": 0.67,
                    "max_drawdown_account": 0.0,
                    "winrate": 1.0,
                    "holding_avg_s": 7680,
                    "winning_days": 2,
                    "draw_days": 0,
                    "losing_days": 0,
                    "backtest_days": 60,
                }
            },
            "strategy_comparison": [{"key": "NostalgiaForInfinityX7"}],
        }

        metrics = parse_backtest_payload(payload, source="sample.json")

        self.assertEqual(metrics.strategy, "NostalgiaForInfinityX7")
        self.assertEqual(metrics.source, "sample.json")
        self.assertEqual(metrics.trades, 2)
        self.assertEqual(metrics.profit_factor, 1.8)
        self.assertEqual(metrics.max_drawdown_pct, 0.0)
        self.assertEqual(metrics.winrate, 1.0)
```

Update imports:

```python
from scripts.score_backtests import confidence_label, parse_backtest_payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: FAIL with `ImportError` for `parse_backtest_payload`.

- [ ] **Step 3: Implement dataclass and parser**

Replace `scripts/score_backtests.py` with:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/score_backtests.py tests/test_score_backtests.py
git commit -m "feat: parse freqtrade backtest metrics"
```

## Task 3: Risk Score and Recommendation

**Files:**
- Modify: `scripts/score_backtests.py`
- Modify: `tests/test_score_backtests.py`

- [ ] **Step 1: Add failing scoring tests**

Append inside `ScoreBacktestsTests`:

```python
    def test_score_penalizes_low_trade_count_and_drawdown(self):
        low_sample = BacktestMetrics(
            source="low.json",
            strategy="NFI",
            trades=2,
            profit_factor=3.0,
            profit_total_pct=10.0,
            max_drawdown_pct=0.0,
            winrate=1.0,
            avg_duration_seconds=3600,
            winning_days=2,
            draw_days=0,
            losing_days=0,
            backtest_days=60,
        )
        risky = BacktestMetrics(
            source="risky.json",
            strategy="NFI",
            trades=120,
            profit_factor=1.3,
            profit_total_pct=12.0,
            max_drawdown_pct=22.0,
            winrate=0.58,
            avg_duration_seconds=7200,
            winning_days=20,
            draw_days=4,
            losing_days=10,
            backtest_days=60,
        )

        self.assertEqual(score_backtest(low_sample).confidence, "LOW")
        self.assertLess(score_backtest(low_sample).score, 60)
        self.assertLess(score_backtest(risky).score, 70)

    def test_recommendation_prefers_collect_more_data_for_low_confidence(self):
        metrics = BacktestMetrics(
            source="low.json",
            strategy="NFI",
            trades=2,
            profit_factor=3.0,
            profit_total_pct=10.0,
            max_drawdown_pct=0.0,
            winrate=1.0,
            avg_duration_seconds=3600,
            winning_days=2,
            draw_days=0,
            losing_days=0,
            backtest_days=60,
        )

        result = score_backtest(metrics)

        self.assertEqual(result.recommendation, "COLLECT_MORE_DATA")
```

Update imports:

```python
from scripts.score_backtests import (
    BacktestMetrics,
    confidence_label,
    parse_backtest_payload,
    score_backtest,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: FAIL with `ImportError` for `score_backtest`.

- [ ] **Step 3: Implement scoring**

Append to `scripts/score_backtests.py`:

```python
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
    if active_days and metrics.winning_days / active_days >= 0.65:
        score += 7
    elif active_days and metrics.losing_days / active_days >= 0.45:
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
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/score_backtests.py tests/test_score_backtests.py
git commit -m "feat: score backtests by risk-adjusted quality"
```

## Task 4: CLI Report Generation

**Files:**
- Modify: `scripts/score_backtests.py`
- Modify: `tests/test_score_backtests.py`
- Create: `reports/README.md`

- [ ] **Step 1: Add failing report rendering test**

Append inside `ScoreBacktestsTests`:

```python
    def test_markdown_report_states_not_live_recommendation(self):
        metrics = BacktestMetrics(
            source="sample.json",
            strategy="NFI",
            trades=2,
            profit_factor=1.8,
            profit_total_pct=0.67,
            max_drawdown_pct=0.0,
            winrate=1.0,
            avg_duration_seconds=7680,
            winning_days=2,
            draw_days=0,
            losing_days=0,
            backtest_days=60,
        )

        markdown = render_markdown_report([score_backtest(metrics)])

        self.assertIn("not a live trading recommendation", markdown)
        self.assertIn("COLLECT_MORE_DATA", markdown)
        self.assertIn("LOW", markdown)
```

Update imports to include `render_markdown_report`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: FAIL with `ImportError` for `render_markdown_report`.

- [ ] **Step 3: Implement report rendering and CLI**

Append to `scripts/score_backtests.py`:

```python
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


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
    json_path.write_text(json.dumps([score_to_dict(item) for item in scores], indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(scores), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
```

Create `reports/README.md`:

```markdown
# Reports

This directory is for small generated risk-score reports.

Raw Freqtrade backtest artifacts stay under `user_data/backtest_results/` and remain ignored because they can become large and noisy.

Risk-score reports are research aids only. They are not live trading recommendations.
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_score_backtests -v`

Expected: PASS, 5 tests.

- [ ] **Step 5: Run CLI on existing local backtest**

Run:

```bash
python scripts/score_backtests.py user_data/backtest_results/backtest-result-2026-05-03_16-21-24.json --output-dir reports
```

Expected:

```text
Wrote reports/risk-score-2026-05-03.json
Wrote reports/risk-score-2026-05-03.md
```

The Markdown report includes `COLLECT_MORE_DATA` and `LOW`.

- [ ] **Step 6: Commit**

```bash
git add scripts/score_backtests.py tests/test_score_backtests.py reports/README.md reports/risk-score-2026-05-03.json reports/risk-score-2026-05-03.md
git commit -m "feat: generate risk score reports"
```

## Task 5: CI and Documentation

**Files:**
- Modify: `.github/workflows/repo-safety.yml`
- Modify: `README.md`
- Modify: `scripts/check_repo_safety.py`

- [ ] **Step 1: Add test command to CI workflow**

Modify `.github/workflows/repo-safety.yml` to:

```yaml
name: Repo Safety

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  safety:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Run repository safety checks
        run: python scripts/check_repo_safety.py

      - name: Run unit tests
        run: python -m unittest discover -s tests -v
```

- [ ] **Step 2: Update safety script to validate report JSON if committed**

In `scripts/check_repo_safety.py`, add `"reports/README.md"` is not required. Add this function:

```python
def check_report_json_files(tracked: list[str]) -> None:
    for path in tracked:
        if path.startswith("reports/risk-score-") and path.endswith(".json"):
            data = json.loads(read(path))
            if not isinstance(data, list):
                fail(f"report JSON must contain a list: {path}")
            for item in data:
                if item.get("recommendation") not in {
                    "KEEP_CURRENT",
                    "EXPAND_PAIRLIST",
                    "TIGHTEN_PAIRLIST",
                    "COLLECT_MORE_DATA",
                    "DO_NOT_CHANGE_YET",
                }:
                    fail(f"invalid report recommendation in {path}")
```

Call it from `main()` after `check_json_templates()`:

```python
    check_report_json_files(tracked)
```

- [ ] **Step 3: Update README command**

Replace the safety command section in `README.md` with:

```markdown
Run repository checks:

```bash
python scripts/check_repo_safety.py
python -m unittest discover -s tests -v
```

Generate a risk-score report from a Freqtrade backtest JSON:

```bash
python scripts/score_backtests.py user_data/backtest_results/backtest-result-YYYY-MM-DD_HH-MM-SS.json --output-dir reports
```
```

- [ ] **Step 4: Run full verification**

Run:

```bash
python scripts/check_repo_safety.py
python -m unittest discover -s tests -v
```

Expected:

```text
PASS: repository safety checks passed
...
OK
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/repo-safety.yml README.md scripts/check_repo_safety.py
git commit -m "ci: test risk scoring reports"
```

## Task 6: Final Verification and Push

**Files:**
- No code changes unless verification reveals a defect.

- [ ] **Step 1: Run final local verification**

Run:

```bash
python scripts/check_repo_safety.py
python -m unittest discover -s tests -v
git status --short --branch
```

Expected:

```text
PASS: repository safety checks passed
...
OK
## main...origin/main [ahead N]
```

- [ ] **Step 2: Push**

Run:

```bash
git push
```

Expected: push succeeds.

- [ ] **Step 3: Confirm remote HEAD**

Run:

```bash
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected: both SHAs match.

## Self-Review

- Spec coverage: scoring, confidence labels, reports, low-sample handling, safety rules, and no strategy changes are covered.
- Placeholder scan: no placeholder work remains; every task has commands and expected outcomes.
- Type consistency: `BacktestMetrics`, `BacktestScore`, `score_backtest`, `parse_backtest_payload`, and `render_markdown_report` are defined before use.
- Scope check: this plan intentionally does not run new backtests or tune pairlists; it builds the scoring/reporting layer first.
