import unittest
from datetime import datetime
from unittest.mock import Mock

from trading_harness.market_data.nse_auto_poller import NSEAutoPoller


class TestNSEAutoPoller(unittest.TestCase):
    def test_manual_poll_does_not_shift_aligned_schedule(self):
        collector = Mock()
        collector.run_single_cycle.return_value = {"status": "SUCCESS"}
        collector.get_ist_now.return_value = datetime(2026, 11, 5, 10, 0)
        poller = NSEAutoPoller(collector)
        next_poll = datetime(2026, 11, 5, 10, 5)
        poller._next_poll_at = next_poll

        result = poller.poll_now()
        status = poller.get_status()

        self.assertEqual(result["status"], "SUCCESS")
        collector.run_single_cycle.assert_called_once_with(force=True)
        self.assertEqual(status["last_poll_at"], datetime(2026, 11, 5, 10, 0))
        self.assertEqual(status["last_result"]["status"], "SUCCESS")
        self.assertEqual(status["next_poll_at"], next_poll)

    def test_next_poll_follows_fixed_five_minute_clock_marks(self):
        poller = NSEAutoPoller(Mock(), interval_seconds=300)
        cases = [
            (datetime(2026, 11, 5, 9, 2, 30), datetime(2026, 11, 5, 9, 5)),
            (datetime(2026, 11, 5, 9, 5), datetime(2026, 11, 5, 9, 10)),
            (datetime(2026, 11, 5, 9, 58), datetime(2026, 11, 5, 10, 0)),
            (datetime(2026, 11, 5, 23, 59), datetime(2026, 11, 6, 0, 0)),
        ]

        for current, expected in cases:
            with self.subTest(current=current):
                self.assertEqual(poller._next_aligned_poll(current), expected)

    def test_archive_uses_same_lock_as_polls(self):
        collector = Mock()
        collector.archive_running_file.return_value = "data/archive/snapshot.csv"
        poller = NSEAutoPoller(collector)

        result = poller.archive_now()

        self.assertEqual(result, "data/archive/snapshot.csv")
        collector.archive_running_file.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
