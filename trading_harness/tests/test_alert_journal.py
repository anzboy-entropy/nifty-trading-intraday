import csv
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from trading_harness.alert_journal import TradeAlertJournal, group_alert_episodes


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

    def test_date_partitioned_journal_loads_only_current_day_timestamps(self):
        archive_dir = os.path.join(self.temp_dir.name, "archive")
        base_path = os.path.join(self.temp_dir.name, "trade_alerts.csv")
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        yesterday = today - timedelta(days=1)
        current_record = {
            key: value for key, value in self.setup.items() if key != "timestamp"
        }
        current_record["snapshot_ist"] = f"{today.isoformat()} 10:15:00"
        old_record = dict(current_record)
        old_record["snapshot_ist"] = f"{yesterday.isoformat()} 10:15:00"

        os.makedirs(archive_dir)
        for path, record in (
            (os.path.join(self.temp_dir.name, f"trade_alerts_{today}.csv"), current_record),
            (os.path.join(archive_dir, f"trade_alerts_{yesterday}.csv"), old_record),
        ):
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=TradeAlertJournal.FIELDNAMES)
                writer.writeheader()
                writer.writerow(record)

        journal = TradeAlertJournal(
            base_path,
            archive_dir=archive_dir,
            date_partitioned=True,
        )

        self.assertIn(
            (today.isoformat(), "RELIANCE", "Momentum Trading", "BUY"),
            journal._episode_seen_at,
        )
        self.assertNotIn(
            (yesterday.isoformat(), "RELIANCE", "Momentum Trading", "BUY"),
            journal._episode_seen_at,
        )

    def test_price_updates_are_suppressed_until_a_new_episode(self):
        journal = TradeAlertJournal(self.path)

        self.assertTrue(journal.log_alert(self.setup))
        changed_entry = dict(
            self.setup,
            timestamp="2026-11-05 10:20:00",
            entry_price=1001.0,
        )
        new_episode = dict(
            self.setup,
            timestamp="2026-11-05 10:36:00",
        )

        self.assertFalse(journal.log_alert(changed_entry))
        self.assertTrue(journal.log_alert(new_episode))
        self.assertFalse(journal.log_alert(new_episode))

        with open(self.path, "r", newline="", encoding="utf-8") as file:
            records = list(csv.DictReader(file))
        self.assertEqual(len(records), 2)

    def test_groups_snapshot_rows_into_strategy_episodes(self):
        records = [
            dict(self.setup, timestamp="2026-11-05 10:15:00"),
            dict(
                self.setup,
                timestamp="2026-11-05 10:20:00",
                strategy="VWAP Trading",
                entry_price=1001.0,
            ),
            dict(
                self.setup,
                timestamp="2026-11-05 10:25:00",
                entry_price=1002.0,
            ),
            dict(
                self.setup,
                timestamp="2026-11-05 10:45:00",
                entry_price=1005.0,
            ),
        ]

        episodes = group_alert_episodes(records)

        self.assertEqual(len(episodes), 2)
        self.assertEqual(episodes[0]["start_timestamp"], "2026-11-05 10:45:00")
        self.assertEqual(episodes[0]["updates"], 1)
        self.assertEqual(episodes[1]["start_timestamp"], "2026-11-05 10:15:00")
        self.assertEqual(episodes[1]["last_seen"], "2026-11-05 10:25:00")
        self.assertEqual(episodes[1]["updates"], 3)
        self.assertEqual(
            episodes[1]["strategies"],
            ["Momentum Trading", "VWAP Trading"],
        )
        self.assertEqual(
            episodes[1]["strategy_rationales"],
            {
                "Momentum Trading": self.setup["rationale"],
                "VWAP Trading": self.setup["rationale"],
            },
        )

    def test_date_partitioned_journal_archives_completed_day(self):
        archive_dir = os.path.join(self.temp_dir.name, "archive")
        journal = TradeAlertJournal(
            os.path.join(self.temp_dir.name, "trade_alerts.csv"),
            archive_dir=archive_dir,
            date_partitioned=True,
        )
        now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        file_date = now.date() + timedelta(days=1)
        setup = dict(self.setup, timestamp=f"{file_date.isoformat()} 10:15:00")

        self.assertTrue(journal.log_alert(setup))
        daily_path = journal._path_for_date(file_date.isoformat())
        self.assertIn(file_date.isoformat(), os.path.basename(daily_path))
        self.assertTrue(os.path.exists(daily_path))

        after_close = now.replace(
            year=file_date.year,
            month=file_date.month,
            day=file_date.day,
            hour=16,
            minute=0,
            second=0,
            microsecond=0,
        )
        archived = journal.archive_expired_files(now=after_close, include_current=True)

        self.assertEqual(archived, [os.path.join(archive_dir, os.path.basename(daily_path))])
        self.assertFalse(os.path.exists(daily_path))
        self.assertTrue(os.path.exists(archived[0]))


if __name__ == "__main__":
    unittest.main()
