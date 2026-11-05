import unittest

import pandas as pd

from trading_harness.market_data.snapshot_candles import synthesize_5m_candles


class TestSnapshotCandles(unittest.TestCase):
    def test_builds_estimated_bars_from_adjacent_snapshots_and_volume_deltas(self):
        snapshots = pd.DataFrame([
            ("2026-11-05 09:15:05", "RELIANCE", 100.0, 1000, 110.0, 90.0),
            ("2026-11-05 09:20:04", "RELIANCE", 102.0, 1150, 110.0, 90.0),
            ("2026-11-05 09:25:06", "RELIANCE", 101.0, 1230, 110.0, 90.0),
            ("2026-11-05 09:35:02", "RELIANCE", 104.0, 1400, 110.0, 90.0),
        ], columns=[
            "snapshot_ist", "symbol", "last_price", "volume", "day_high", "day_low"
        ])

        candles = synthesize_5m_candles(snapshots, "RELIANCE")

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles.iloc[0]["timestamp"], pd.Timestamp(
            "2026-11-05 09:15", tz="Asia/Kolkata"
        ))
        self.assertEqual(
            candles.iloc[0][["open", "high", "low", "close", "volume"]].tolist(),
            [100.0, 102.0, 100.0, 102.0, 150.0],
        )
        self.assertEqual(
            candles.iloc[1][["open", "high", "low", "close", "volume"]].tolist(),
            [102.0, 102.0, 101.0, 101.0, 80.0],
        )
        self.assertFalse(candles.attrs["verified_ohlcv"])
        self.assertEqual(candles.attrs["data_source"], "synthetic_estimate")

    def test_does_not_bridge_missing_snapshots_or_volume_resets(self):
        snapshots = pd.DataFrame([
            ("2026-11-05 09:15:00", "RELIANCE", 100.0, 1000),
            ("2026-11-05 09:20:00", "RELIANCE", 101.0, 900),
            ("2026-11-05 09:25:00", "RELIANCE", 102.0, 950),
            ("2026-11-05 09:35:00", "RELIANCE", 104.0, 1100),
        ], columns=["snapshot_ist", "symbol", "last_price", "volume"])

        candles = synthesize_5m_candles(snapshots, "RELIANCE")

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles.iloc[0]["timestamp"], pd.Timestamp(
            "2026-11-05 09:20", tz="Asia/Kolkata"
        ))
        self.assertEqual(candles.iloc[0]["volume"], 50.0)

    def test_ignores_unaligned_snapshots_and_other_symbols(self):
        snapshots = pd.DataFrame([
            ("2026-11-05 09:15:00", "RELIANCE", 100.0, 1000),
            ("2026-11-05 09:20:00", "TCS", 200.0, 1000),
            ("2026-11-05 09:22:30", "RELIANCE", 101.0, 1100),
        ], columns=["snapshot_ist", "symbol", "last_price", "volume"])

        candles = synthesize_5m_candles(snapshots, "RELIANCE")

        self.assertTrue(candles.empty)
        self.assertFalse(candles.attrs["verified_ohlcv"])


if __name__ == "__main__":
    unittest.main()
