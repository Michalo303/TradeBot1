import unittest

from scripts.score_backtests import (
    BacktestMetrics,
    confidence_label,
    parse_backtest_payload,
    render_markdown_report,
    score_backtest,
)


class ScoreBacktestsTests(unittest.TestCase):
    def test_confidence_label_uses_trade_count_thresholds(self):
        self.assertEqual(confidence_label(0, incomplete=False), "LOW")
        self.assertEqual(confidence_label(29, incomplete=False), "LOW")
        self.assertEqual(confidence_label(30, incomplete=False), "MEDIUM")
        self.assertEqual(confidence_label(99, incomplete=False), "MEDIUM")
        self.assertEqual(confidence_label(100, incomplete=False), "HIGH")
        self.assertEqual(confidence_label(100, incomplete=True), "LOW")


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


    def test_score_penalizes_low_trade_count_and_drawdown(self):
        low_sample = BacktestMetrics(
            source="low.json", strategy="NFI", trades=2, profit_factor=3.0,
            profit_total_pct=10.0, max_drawdown_pct=0.0, winrate=1.0,
            avg_duration_seconds=3600, winning_days=2, draw_days=0,
            losing_days=0, backtest_days=60,
        )
        risky = BacktestMetrics(
            source="risky.json", strategy="NFI", trades=120, profit_factor=1.3,
            profit_total_pct=12.0, max_drawdown_pct=22.0, winrate=0.58,
            avg_duration_seconds=7200, winning_days=20, draw_days=4,
            losing_days=10, backtest_days=60,
        )

        self.assertEqual(score_backtest(low_sample).confidence, "LOW")
        self.assertLess(score_backtest(low_sample).score, 60)
        self.assertLess(score_backtest(risky).score, 70)

    def test_recommendation_prefers_collect_more_data_for_low_confidence(self):
        metrics = BacktestMetrics(
            source="low.json", strategy="NFI", trades=2, profit_factor=3.0,
            profit_total_pct=10.0, max_drawdown_pct=0.0, winrate=1.0,
            avg_duration_seconds=3600, winning_days=2, draw_days=0,
            losing_days=0, backtest_days=60,
        )

        result = score_backtest(metrics)

        self.assertEqual(result.recommendation, "COLLECT_MORE_DATA")


    def test_markdown_report_states_not_live_recommendation(self):
        metrics = BacktestMetrics(
            source="sample.json", strategy="NFI", trades=2, profit_factor=1.8,
            profit_total_pct=0.67, max_drawdown_pct=0.0, winrate=1.0,
            avg_duration_seconds=7680, winning_days=2, draw_days=0,
            losing_days=0, backtest_days=60,
        )

        markdown = render_markdown_report([score_backtest(metrics)])

        self.assertIn("not a live trading recommendation", markdown)
        self.assertIn("COLLECT_MORE_DATA", markdown)
        self.assertIn("LOW", markdown)


if __name__ == "__main__":
    unittest.main()
