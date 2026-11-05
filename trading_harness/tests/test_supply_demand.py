import unittest

import pandas as pd

from trading_harness.scanner_engine import LiveScannerEngine
from trading_harness.strategies.supply_demand import SupplyDemandStrategy


class TestSupplyDemandStrategy(unittest.TestCase):
    def setUp(self):
        timestamps = pd.date_range(
            "2026-11-05 09:15",
            periods=45,
            freq="5min",
            tz="Asia/Kolkata",
        )
        self.candles = pd.DataFrame({
            "timestamp": timestamps,
            "open": [100.0] * len(timestamps),
            "high": [101.0] * len(timestamps),
            "low": [99.0] * len(timestamps),
            "close": [100.0] * len(timestamps),
            "volume": [1000] * len(timestamps),
        })

    def test_requires_verified_5_minute_ohlcv_and_timezone(self):
        self.candles.attrs.update({
            "verified_ohlcv": False,
            "timeframe": None,
            "timezone": "Asia/Kolkata",
        })
        self.assertIsNone(SupplyDemandStrategy().evaluate(self.candles))

        self.candles.attrs.update({
            "verified_ohlcv": True,
            "timeframe": "5m",
            "timezone": "UTC",
        })
        self.assertIsNone(SupplyDemandStrategy().evaluate(self.candles))

    def test_rejects_missing_intervals(self):
        self.candles = self.candles.drop(index=20).reset_index(drop=True)
        self.candles.attrs.update({
            "verified_ohlcv": True,
            "timeframe": "5m",
            "timezone": "Asia/Kolkata",
        })
        self.assertIsNone(SupplyDemandStrategy().evaluate(self.candles))

    def test_accepts_verified_complete_session_and_aggregates_context(self):
        self.candles.attrs.update({
            "verified_ohlcv": True,
            "timeframe": "5m",
            "timezone": "Asia/Kolkata",
        })

        validated = SupplyDemandStrategy._validated_session(self.candles)

        self.assertIsNotNone(validated)
        self.assertEqual(validated[1]["bias"], "neutral")

    def test_estimated_session_requires_explicit_opt_in(self):
        self.candles.attrs.update({
            "verified_ohlcv": False,
            "data_source": "synthetic_estimate",
            "timeframe": "5m",
            "timezone": "Asia/Kolkata",
        })
        self.assertIsNone(SupplyDemandStrategy._validated_session(self.candles))

        self.candles.attrs["allow_estimated_ohlcv"] = True
        self.assertIsNotNone(SupplyDemandStrategy._validated_session(self.candles))

    def test_detects_zone_after_departure_volume_and_structure_break(self):
        centers = [
            100, 102, 100, 101, 100, 101.5, 99.8, 102, 100, 101.2,
            99.9, 102.2, 100, 101.3, 100, 102.4, 100, 101.3, 100, 102.5,
        ]
        rows = [
            {"open": price, "high": price + 0.2, "low": price - 0.2,
             "close": price, "volume": 1000}
            for price in centers
        ]
        rows.extend([
            {"open": 100, "high": 100.2, "low": 99.8, "close": 100, "volume": 1000},
            {"open": 100, "high": 100.2, "low": 99.8, "close": 100, "volume": 1000},
            {"open": 100, "high": 104.5, "low": 100, "close": 104, "volume": 2500},
        ])
        rows.extend([
            {"open": 104, "high": 105, "low": 103.8, "close": 104.8, "volume": 1000}
            for _ in range(22)
        ])
        candles = pd.DataFrame(rows)

        zones = SupplyDemandStrategy()._find_zones(candles)

        self.assertTrue(any(
            zone["type"] == "demand"
            and zone["base_start"] == 20
            and zone["created"] == 22
            for zone in zones
        ))

    def test_emits_risk_qualified_signal_on_confirmed_zone_retest(self):
        rows = [
            {"open": price, "high": price + 0.2, "low": price - 0.2,
             "close": price, "volume": 1000}
            for price in [
                100, 102, 100, 101, 100, 101.5, 99.8, 102, 100, 101.2,
                99.9, 102.2, 100, 101.3, 100, 102.4, 100, 101.3, 100, 102.5,
            ]
        ]
        rows.extend([
            {"open": 100, "high": 100.2, "low": 99.8, "close": 100, "volume": 1000},
            {"open": 100, "high": 100.2, "low": 99.8, "close": 100, "volume": 1000},
            {"open": 100, "high": 104.5, "low": 100, "close": 104, "volume": 2500},
            {"open": 104, "high": 105, "low": 103.8, "close": 104.8, "volume": 1000},
            {"open": 104.8, "high": 107, "low": 104.5, "close": 106.8, "volume": 1000},
            {"open": 106.8, "high": 107, "low": 105.5, "close": 106, "volume": 1000},
            {"open": 106, "high": 106.2, "low": 105, "close": 105.5, "volume": 1000},
            {"open": 105.5, "high": 105.7, "low": 105.1, "close": 105.4, "volume": 1000},
            {"open": 105.4, "high": 105.6, "low": 101, "close": 101.5, "volume": 2500},
        ])
        rows.extend([
            {"open": 102, "high": 103, "low": 101, "close": 102, "volume": 1000}
            for _ in range(10)
        ])
        rows.append({"open": 101, "high": 102, "low": 99.9, "close": 100, "volume": 1000})
        rows.extend([
            {"open": 102, "high": 103, "low": 101, "close": 102, "volume": 1000}
            for _ in range(15)
        ])
        rows.append({"open": 100.1, "high": 100.8, "low": 99.6, "close": 100.5, "volume": 3000})
        candles = pd.DataFrame(rows)
        candles.insert(
            0,
            "timestamp",
            pd.date_range(
                "2026-11-05 09:15",
                periods=len(candles),
                freq="5min",
                tz="Asia/Kolkata",
            ),
        )
        candles.attrs.update({
            "verified_ohlcv": True,
            "timeframe": "5m",
            "timezone": "Asia/Kolkata",
            "tick_size": 0.05,
        })

        signal = SupplyDemandStrategy().evaluate(candles)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["strategy"], "Supply & Demand (5m)")
        self.assertEqual(signal["side"], "BUY")
        self.assertGreaterEqual(
            (signal["target"] - signal["entry"])
            / (signal["entry"] - signal["stop_loss"]),
            2.0,
        )

    def test_estimated_signal_is_labeled_and_confidence_is_capped(self):
        rows = [
            {"open": price, "high": price + 0.2, "low": price - 0.2,
             "close": price, "volume": 1000}
            for price in [
                100, 102, 100, 101, 100, 101.5, 99.8, 102, 100, 101.2,
                99.9, 102.2, 100, 101.3, 100, 102.4, 100, 101.3, 100, 102.5,
            ]
        ]
        rows.extend([
            {"open": 100, "high": 100.2, "low": 99.8, "close": 100, "volume": 1000},
            {"open": 100, "high": 100.2, "low": 99.8, "close": 100, "volume": 1000},
            {"open": 100, "high": 104.5, "low": 100, "close": 104, "volume": 2500},
            {"open": 104, "high": 105, "low": 103.8, "close": 104.8, "volume": 1000},
            {"open": 104.8, "high": 107, "low": 104.5, "close": 106.8, "volume": 1000},
            {"open": 106.8, "high": 107, "low": 105.5, "close": 106, "volume": 1000},
            {"open": 106, "high": 106.2, "low": 105, "close": 105.5, "volume": 1000},
            {"open": 105.5, "high": 105.7, "low": 105.1, "close": 105.4, "volume": 1000},
            {"open": 105.4, "high": 105.6, "low": 101, "close": 101.5, "volume": 2500},
        ])
        rows.extend([
            {"open": 102, "high": 103, "low": 101, "close": 102, "volume": 1000}
            for _ in range(10)
        ])
        rows.append({"open": 101, "high": 102, "low": 99.9, "close": 100, "volume": 1000})
        rows.extend([
            {"open": 102, "high": 103, "low": 101, "close": 102, "volume": 1000}
            for _ in range(15)
        ])
        rows.append({"open": 100.1, "high": 100.8, "low": 99.6, "close": 100.5, "volume": 3000})
        candles = pd.DataFrame(rows)
        candles.insert(
            0,
            "timestamp",
            pd.date_range(
                "2026-11-05 09:15",
                periods=len(candles),
                freq="5min",
                tz="Asia/Kolkata",
            ),
        )
        candles.attrs.update({
            "verified_ohlcv": False,
            "data_source": "synthetic_estimate",
            "allow_estimated_ohlcv": True,
            "timeframe": "5m",
            "timezone": "Asia/Kolkata",
            "tick_size": 0.05,
        })

        signal = SupplyDemandStrategy().evaluate(candles)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["data_quality"], "ESTIMATED")
        self.assertEqual(signal["confidence"], "MEDIUM")
        self.assertIn("ESTIMATED snapshot-derived bars", signal["rationale"])

        scanner = LiveScannerEngine()
        enriched = scanner._enrich_indicators(candles.copy())
        enriched.attrs.update(candles.attrs)
        setups = scanner.scan_symbol_setups(
            enriched,
            "RELIANCE",
            active_strategies=["Supply & Demand (5m)"],
        )

        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0]["data_quality"], "ESTIMATED")
        self.assertEqual(setups[0]["confidence"], "MEDIUM")

    def test_current_snapshot_series_cannot_emit_supply_demand(self):
        snapshots = pd.DataFrame([
            {
                "snapshot_ist": f"2026-11-05 09:{minute:02d}:00",
                "symbol": "RELIANCE",
                "last_price": 100.0 + index,
                "day_high": 102.0 + index,
                "day_low": 98.0 + index,
                "open": 100.0,
                "prev_close": 99.0,
                "volume": 10000 + index * 100,
            }
            for index, minute in enumerate((15, 20, 25))
        ])
        scanner = LiveScannerEngine()
        series = scanner.get_symbol_time_series(snapshots, "RELIANCE")

        setups = scanner.scan_symbol_setups(
            series,
            "RELIANCE",
            active_strategies=["Supply & Demand (5m)"],
        )

        self.assertEqual(series.attrs["data_source"], "nse_daily_snapshots")
        self.assertEqual(setups, [])

    def test_sparse_snapshots_do_not_create_fabricated_scanner_history(self):
        snapshots = pd.DataFrame([
            {
                "snapshot_ist": "2026-11-05 09:15:00",
                "symbol": "RELIANCE",
                "last_price": 100.0,
                "day_high": 102.0,
                "day_low": 98.0,
                "open": 100.0,
                "prev_close": 99.0,
                "volume": 10000,
            },
            {
                "snapshot_ist": "2026-11-05 09:20:00",
                "symbol": "RELIANCE",
                "last_price": 101.0,
                "day_high": 102.0,
                "day_low": 98.0,
                "open": 100.0,
                "prev_close": 99.0,
                "volume": 10100,
            },
        ])

        series = LiveScannerEngine().get_symbol_time_series(snapshots, "RELIANCE")

        self.assertTrue(series.empty)


if __name__ == "__main__":
    unittest.main()
