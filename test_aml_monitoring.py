
import unittest
import pandas as pd

from aml_monitoring import (
    structuring,
    passthrough,
    hr_wire,
    score,
    grid,
)


class TestAMLMonitoring(unittest.TestCase):

    def test_structuring_detects_suspicious_deposits(self):
        df = pd.DataFrame([
            (101, 1, "cash_in", 9000, "US"),
            (101, 2, "cash_in", 9500, "US"),
            (101, 3, "cash_in", 9200, "US"),
            (102, 1, "cash_in", 1000, "US"),
        ], columns=["acct", "day", "type", "amount", "country"])

        alerts = structuring(df, lo=8000, n=3)

        self.assertEqual(alerts, {101})

    def test_passthrough_detects_fund_movement(self):
        df = pd.DataFrame([
            (201, 1, "wire_in", 20000, "US"),
            (201, 1, "wire_out", 19000, "US"),
            (202, 1, "wire_in", 20000, "US"),
            (202, 1, "wire_out", 5000, "US"),
        ], columns=["acct", "day", "type", "amount", "country"])

        alerts = passthrough(df, amt=10000, ratio=0.9)

        self.assertEqual(alerts, {201})

    def test_high_risk_wire_detection(self):
        df = pd.DataFrame([
            (301, 1, "wire_out", 15000, "IR"),
            (302, 1, "wire_out", 15000, "US"),
            (303, 1, "wire_in", 1000, "KP"),
        ], columns=["acct", "day", "type", "amount", "country"])

        alerts = hr_wire(df, t=5000)

        self.assertEqual(alerts, {301})

    def test_scoring(self):
        alerts = {1, 2, 3}
        truth = {1, 2, 4}

        result = score(alerts, truth)

        self.assertEqual(result["tp"], 2)
        self.assertEqual(result["fp"], 1)
        self.assertEqual(result["precision"], 0.667)
        self.assertEqual(result["recall"], 0.667)
        self.assertEqual(result["f1"], 0.667)

    def test_parameter_grid(self):
        result = grid({
            "lo": [7000, 8000],
            "n": [2, 3]
        })

        self.assertEqual(len(result), 4)
        self.assertIn({"lo": 7000, "n": 2}, result)
        self.assertIn({"lo": 8000, "n": 3}, result)


if __name__ == "__main__":
    unittest.main()
