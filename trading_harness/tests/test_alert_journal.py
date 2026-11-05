import csv
import os
import tempfile
import unittest

from trading_harness.alert_journal import TradeAlertJournal


class TestTradeAlertJournal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "trade_alerts.csv")
        self.setup = {
            "timestamp": "2026-11-05 10:15:00",
            "symbol": "RELIANCE",
            "strategy": "Momentum Trading",
            "side": "BUY",
            "entry_price": 1000.0,
            "stop_loss": 992.0,
            "target": 1016.0,
            "risk_reward": "1:2.0",
            "quantity": 150,
            "confidence": "HIGH",
            "max_risk_inr": 1200.0,
            "potential_reward_inr": 2400.0,
            "rationale": "Price above VWAP with increased volume",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_logs_setup_once_and_keeps_original_details(self):
        journal = TradeAlertJournal(self.path)

        self.assertTrue(journal.log_alert(self.setup))
        later_setup = dict(self.setup, timestamp="2026-11-05 10:20:00")
        self.assertFalse(journal.log_alert(later_setup))

        with open(self.path, "r", newline="", encoding="utf-8") as file:
            records = list(csv.DictReader(file))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["snapshot_ist"], self.setup["timestamp"])
        self.assertEqual(float(records[0]["entry_price"]), self.setup["entry_price"])
        self.assertEqual(records[0]["rationale"], self.setup["rationale"])

    def test_deduplicates_after_journal_is_reopened(self):
        self.assertTrue(TradeAlertJournal(self.path).log_alert(self.setup))

        reopened_journal = TradeAlertJournal(self.path)
        self.assertFalse(reopened_journal.log_alert(self.setup))

    def test_changed_entry_or_target_is_a_distinct_alert(self):
        journal = TradeAlertJournal(self.path)

        self.assertTrue(journal.log_alert(self.setup))
        changed_entry = dict(self.setup, entry_price=1001.0)
        changed_target = dict(self.setup, target=1018.0)

        self.assertTrue(journal.log_alert(changed_entry))
        self.assertTrue(journal.log_alert(changed_target))
        self.assertFalse(journal.log_alert(changed_entry))

        with open(self.path, "r", newline="", encoding="utf-8") as file:
            records = list(csv.DictReader(file))
        self.assertEqual(len(records), 3)


if __name__ == "__main__":
    unittest.main()
