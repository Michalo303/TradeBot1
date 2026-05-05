import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_backtest_matrix import validate_manifest


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


if __name__ == "__main__":
    unittest.main()
