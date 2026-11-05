import unittest
from datetime import datetime
from unittest.mock import Mock

from trading_harness.market_data.nse_auto_poller import NSEAutoPoller


class TestNSEAutoPoller(unittest.TestCase):
    def test_manual_poll_records_status_and_schedules_next_poll(self):
        collector = Mock()
        collector.run_single_cycle.return_value = {"status": "SUCCESS"}
        collector.get_ist_now.return_value = datetime(2026, 11, 5, 10, 0)
        poller = NSEAutoPoller(collector)

        result = poller.poll_now()
        status = poller.get_status()

        self.assertEqual(result["status"], "SUCCESS")
        collector.run_single_cycle.assert_called_once_with(force=True)
        self.assertEqual(status["last_poll_at"], datetime(2026, 11, 5, 10, 0))
        self.assertEqual(status["last_result"]["status"], "SUCCESS")
        self.assertIsNotNone(status["next_poll_at"])

    def test_archive_uses_same_lock_as_polls(self):
        collector = Mock()
        collector.archive_running_file.return_value = "data/archive/snapshot.csv"
        poller = NSEAutoPoller(collector)

        result = poller.archive_now()

        self.assertEqual(result, "data/archive/snapshot.csv")
        collector.archive_running_file.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
