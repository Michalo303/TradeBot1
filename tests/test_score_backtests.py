import unittest

from scripts.score_backtests import confidence_label, parse_backtest_payload


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


if __name__ == "__main__":
    unittest.main()
