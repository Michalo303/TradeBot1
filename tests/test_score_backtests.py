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
