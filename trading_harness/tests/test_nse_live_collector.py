import unittest
from unittest.mock import patch

from trading_harness.market_data.nse_live_collector import NSELiveCollector


class TestNSELiveCollectorFetch(unittest.TestCase):
    def test_non_success_http_response_is_reported_after_retries(self):
        class Response:
            status_code = 503
            text = "service unavailable"

        class Session:
            def __init__(self):
                self.calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                return Response()

        collector = NSELiveCollector.__new__(NSELiveCollector)
        collector.session = Session()

        with patch("trading_harness.market_data.nse_live_collector.time.sleep"):
            success, records, error = collector.fetch_snapshot(retries=2)

        self.assertFalse(success)
        self.assertEqual(records, [])
        self.assertEqual(error, "NSE returned HTTP 503: service unavailable")
        self.assertEqual(collector.session.calls, 3)


if __name__ == "__main__":
    unittest.main()
