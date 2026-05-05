import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_backtest_matrix import validate_manifest, build_docker_cmd, score_cell, CellResult, render_matrix_summary


class ValidateManifestTests(unittest.TestCase):
    def test_missing_variant_raises(self):
        with self.assertRaises(ValueError):
            validate_manifest({"pairs": ["BTC/USDT"]})

    def test_empty_variant_raises(self):
        with self.assertRaises(ValueError):
            validate_manifest({"variant": "", "pairs": ["BTC/USDT"]})

    def test_missing_pairs_raises(self):
        with self.assertRaises(ValueError):
            validate_manifest({"variant": "conservative"})

    def test_empty_pairs_raises(self):
        with self.assertRaises(ValueError):
            validate_manifest({"variant": "conservative", "pairs": []})

    def test_valid_manifest_returns_dict(self):
        data = {"variant": "conservative", "pairs": ["BTC/USDT", "ETH/USDT"]}
        result = validate_manifest(data)
        self.assertEqual(result["variant"], "conservative")
        self.assertEqual(result["pairs"], ["BTC/USDT", "ETH/USDT"])


class CLITests(unittest.TestCase):
    def _run_main(self, args):
        with patch("sys.argv", ["run_backtest_matrix"] + args):
            from scripts.run_backtest_matrix import main
            with self.assertRaises(SystemExit) as ctx:
                main()
            return ctx.exception.code

    def test_max_pairs_zero_exits_nonzero(self):
        code = self._run_main(["--max-pairs", "0", "--timerange", "20260101-20260201"])
        self.assertNotEqual(code, 0)

    def test_max_timerange_days_zero_exits_nonzero(self):
        code = self._run_main(["--max-timerange-days", "0", "--timerange", "20260101-20260201"])
        self.assertNotEqual(code, 0)

    def test_max_timerange_days_over_limit_exits_nonzero(self):
        # 366 days > default 365 limit
        code = self._run_main(["--max-timerange-days", "365", "--timerange", "20250101-20260202"])
        self.assertNotEqual(code, 0)

    def test_no_confirm_exits_zero_with_plan(self):
        import io
        import tempfile
        import json
        manifest = {"variant": "test", "pairs": ["BTC/USDT"]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(manifest, f)
            manifest_path = f.name
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = self._run_main([manifest_path, "--timerange", "20260101-20260201"])
        self.assertEqual(code, 0)
        self.assertIn("cell", captured.getvalue().lower())

    def test_pairs_exceeding_max_exits_nonzero(self):
        import tempfile
        import json
        manifest = {"variant": "test", "pairs": ["BTC/USDT", "ETH/USDT", "SOL/USDT"]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(manifest, f)
            manifest_path = f.name
        code = self._run_main([manifest_path, "--timerange", "20260101-20260201", "--max-pairs", "2"])
        self.assertNotEqual(code, 0)


class ScoreCellTests(unittest.TestCase):
    def _make_payload(self, trades=2):
        return {
            "strategy": {
                "NostalgiaForInfinityX7": {
                    "total_trades": trades, "profit_factor": 1.8, "profit_total_pct": 0.67,
                    "max_drawdown_account": 0.0, "winrate": 1.0, "holding_avg_s": 7680,
                    "winning_days": 2, "draw_days": 0, "losing_days": 0, "backtest_days": 60,
                }
            },
            "strategy_comparison": [{"key": "NostalgiaForInfinityX7"}],
        }

    def test_score_cell_calls_load_and_score(self):
        import json, tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self._make_payload(), f)
            path = Path(f.name)
        result = score_cell(path)
        from scripts.score_backtests import BacktestScore
        self.assertIsInstance(result, BacktestScore)

    def test_score_cell_raises_on_invalid_json(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            path = Path(f.name)
        with self.assertRaises(SystemExit):
            score_cell(path)

    def test_score_cell_raises_on_missing_strategy_key(self):
        import json, tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"wrong": "format"}, f)
            path = Path(f.name)
        with self.assertRaises(SystemExit):
            score_cell(path)


class RenderMatrixSummaryTests(unittest.TestCase):
    def _make_cell(self, variant, timerange, trades=2):
        import json, tempfile
        payload = {
            "strategy": {
                "NostalgiaForInfinityX7": {
                    "total_trades": trades, "profit_factor": 1.5, "profit_total_pct": 1.0,
                    "max_drawdown_account": 0.0, "winrate": 1.0, "holding_avg_s": 3600,
                    "winning_days": 2, "draw_days": 0, "losing_days": 0, "backtest_days": 60,
                }
            },
            "strategy_comparison": [{"key": "NostalgiaForInfinityX7"}],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            path = Path(f.name)
        score = score_cell(path)
        return CellResult(variant=variant, timerange=timerange, score=score)

    def test_summary_contains_variant_and_timerange(self):
        cells = [self._make_cell("conservative", "20260101-20260201")]
        md = render_matrix_summary(cells)
        self.assertIn("conservative", md)
        self.assertIn("20260101-20260201", md)

    def test_summary_not_live_trading_recommendation(self):
        cells = [self._make_cell("conservative", "20260101-20260201")]
        md = render_matrix_summary(cells)
        self.assertIn("not a live trading recommendation", md)

    def test_summary_portfolio_disclaimer(self):
        cells = [self._make_cell("conservative", "20260101-20260201")]
        md = render_matrix_summary(cells)
        self.assertIn("portfolio behavior not replicated", md)

    def test_summary_contains_score_confidence_recommendation(self):
        cells = [self._make_cell("conservative", "20260101-20260201")]
        md = render_matrix_summary(cells)
        self.assertIn("Score", md)
        self.assertIn("Confidence", md)
        self.assertIn("Recommendation", md)


class BuildDockerCmdTests(unittest.TestCase):
    BASE_CONFIGS = [
        Path("user_data/config/config.json"),
        Path("user_data/config/config.private.json"),
        Path("user_data/config/blacklist-binance.json"),
    ]

    def _build(self, pairs=None, timerange="20260101-20260201", run_id="abc12345"):
        manifest = {"variant": "test", "pairs": pairs or ["BTC/USDT", "ETH/USDT"]}
        return build_docker_cmd(manifest, timerange, run_id, self.BASE_CONFIGS)

    def test_returns_tuple_of_cmd_and_output_path(self):
        cmd, output_path = self._build()
        self.assertIsInstance(cmd, list)
        self.assertIsInstance(output_path, Path)

    def test_output_path_follows_naming_convention(self):
        _, output_path = self._build(timerange="20260101-20260201", run_id="abc12345")
        self.assertRegex(output_path.name, r"^nfix7-test-20260101-20260201-abc12345\.json$")

    def test_output_path_is_under_backtest_results(self):
        _, output_path = self._build()
        self.assertIn("backtest_results", str(output_path))

    def test_run_id_is_8_chars(self):
        _, output_path = self._build(run_id="deadbeef")
        self.assertIn("deadbeef", output_path.name)

    def test_cmd_contains_freqtrade_image(self):
        cmd, _ = self._build()
        self.assertTrue(any("freqtradeorg/freqtrade" in part for part in cmd))

    def test_cmd_contains_all_config_args(self):
        cmd, _ = self._build()
        cmd_str = " ".join(cmd)
        self.assertIn("config.json", cmd_str)
        self.assertIn("config.private.json", cmd_str)
        self.assertIn("blacklist-binance.json", cmd_str)

    def test_cmd_contains_pairs(self):
        cmd, _ = self._build(pairs=["BTC/USDT", "ETH/USDT"])
        cmd_str = " ".join(cmd)
        self.assertIn("BTC/USDT", cmd_str)
        self.assertIn("ETH/USDT", cmd_str)

    def test_cmd_contains_timerange(self):
        cmd, _ = self._build(timerange="20260101-20260201")
        cmd_str = " ".join(cmd)
        self.assertIn("20260101-20260201", cmd_str)

    def test_cmd_contains_export_filename_with_container_path(self):
        cmd, output_path = self._build()
        cmd_str = " ".join(cmd)
        self.assertIn("/freqtrade/user_data/backtest_results/", cmd_str)
        self.assertIn(output_path.name, cmd_str)

    def test_cmd_contains_export_trades(self):
        cmd, _ = self._build()
        cmd_str = " ".join(cmd)
        self.assertIn("--export", cmd_str)
        self.assertIn("trades", cmd_str)


class SafetyCheckMatrixTests(unittest.TestCase):
    def test_check_repo_safety_passes_without_matrix_in_ci(self):
        import subprocess
        result = subprocess.run(
            ["python", "scripts/check_repo_safety.py"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("PASS", result.stdout)

    def test_check_matrix_not_in_ci_yml_function_exists(self):
        from scripts.check_repo_safety import check_matrix_not_in_ci
        check_matrix_not_in_ci()


if __name__ == "__main__":
    unittest.main()
