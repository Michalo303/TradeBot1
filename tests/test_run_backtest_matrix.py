import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_backtest_matrix import validate_manifest, build_docker_cmd


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


if __name__ == "__main__":
    unittest.main()
