"""
Unit Test Suite for Indian Intraday Trading Harness.
Verifies Risk Engine, Clock Phases, 7 Strategy Evaluators, Broker Fills, and Claude Tools.
"""

import unittest
import os
from datetime import datetime

from trading_harness.config import TradingHarnessConfig, RiskConfig, StatutoryFeeStructure, MarketSessionConfig
from trading_harness.clock import IndianMarketClock
from trading_harness.risk_engine import RiskEngine
from trading_harness.indicators import TechnicalIndicators
from trading_harness.broker.mock_broker import MockBroker
from trading_harness.market_data.feed import MarketDataFeed
from trading_harness.journal import TradeJournal
from trading_harness.claude_agent_interface import ClaudeAgentInterface
from trading_harness.strategies.momentum import MomentumStrategy
from trading_harness.strategies.breakout import BreakoutStrategy
from trading_harness.strategies.reversal import ReversalStrategy
from trading_harness.strategies.vwap import VWAPStrategy
from trading_harness.strategies.scalping import ScalpingStrategy
from trading_harness.strategies.gap_and_go import GapAndGoStrategy
from trading_harness.strategies.orb import OpeningRangeBreakoutStrategy

class TestTradingHarness(unittest.TestCase):
    def setUp(self):
        self.config = TradingHarnessConfig()
        self.clock = IndianMarketClock(self.config.session)
        self.risk_engine = RiskEngine(self.config.risk, self.config.fees, self.clock)
        self.broker = MockBroker(100000.0, self.risk_engine, self.clock)
        self.market_data = MarketDataFeed()
        self.journal = TradeJournal(journal_path="logs/test_journal.json", csv_path="logs/test_journal.csv")
        self.agent_interface = ClaudeAgentInterface(
            self.clock, self.risk_engine, self.broker, self.market_data, self.journal
        )

    def test_clock_phases(self):
        # 09:05 IST -> PRE_OPEN
        self.clock.set_simulated_time(datetime(2026, 11, 4, 9, 5))
        self.assertEqual(self.clock.get_session_phase(), "PRE_OPEN")
        self.assertTrue(self.clock.is_pre_market())
        self.assertFalse(self.clock.is_market_open())

        # 09:20 IST -> MORNING_VOLATILITY
        self.clock.set_simulated_time(datetime(2026, 11, 4, 9, 20))
        self.assertEqual(self.clock.get_session_phase(), "MORNING_VOLATILITY")
        self.assertTrue(self.clock.is_market_open())

        # 12:00 IST -> MIDDAY_CONSOLIDATION
        self.clock.set_simulated_time(datetime(2026, 11, 4, 12, 0))
        self.assertEqual(self.clock.get_session_phase(), "MIDDAY_CONSOLIDATION")

        # 15:20 IST -> MANDATORY_SQUARE_OFF
        self.clock.set_simulated_time(datetime(2026, 11, 4, 15, 20))
        self.assertTrue(self.clock.is_square_off_time())
        self.assertEqual(self.clock.get_session_phase(), "MANDATORY_SQUARE_OFF")

    def test_risk_position_sizing(self):
        # Capital 1,00,000 INR, Risk 1.5% (1500 INR)
        # Entry 500, SL 495 -> Risk per share = 5 INR -> Quantity = 300 shares
        qty = self.risk_engine.calculate_position_size(
            capital=100000.0, entry=500.0, stop_loss=495.0, risk_pct=0.015
        )
        self.assertEqual(qty, 300)

        # Risk capped at max 2%
        qty_max = self.risk_engine.calculate_position_size(
            capital=100000.0, entry=500.0, stop_loss=495.0, risk_pct=0.05
        )
        self.assertEqual(qty_max, 400) # (100000 * 0.02) / 5 = 400

    def test_risk_validation_stop_loss_mandate(self):
        self.clock.set_simulated_time(datetime(2026, 11, 4, 9, 30))
        account = self.broker.get_account_state()

        # Reject order without Stop Loss
        naked_order = {
            "symbol": "SBIN",
            "side": "BUY",
            "quantity": 100,
            "price": 820.0,
            "product": "MIS"
        }
        valid, reason = self.risk_engine.validate_order(naked_order, account)
        self.assertFalse(valid)
        self.assertIn("Stop-Loss is missing", reason)

        # Reject order where Buy Stop-Loss is >= Entry
        invalid_sl_order = {
            "symbol": "SBIN",
            "side": "BUY",
            "quantity": 100,
            "price": 820.0,
            "stop_loss": 825.0, # Invalid for BUY
            "product": "MIS"
        }
        valid, reason = self.risk_engine.validate_order(invalid_sl_order, account)
        self.assertFalse(valid)
        self.assertIn("must be strictly below Entry", reason)

    def test_risk_validation_square_off_time_blocking(self):
        # When 15:20 IST arrives, no new orders should be permitted
        self.clock.set_simulated_time(datetime(2026, 11, 4, 15, 21))
        account = self.broker.get_account_state()
        order = {
            "symbol": "SBIN",
            "side": "BUY",
            "quantity": 10,
            "price": 820.0,
            "stop_loss": 815.0,
            "product": "MIS"
        }
        valid, reason = self.risk_engine.validate_order(order, account)
        self.assertFalse(valid)
        self.assertIn("MIS auto square-off threshold", reason)

    def test_statutory_charges_calculation(self):
        # Test Buy side (no STT, stamp duty applicable, zero brokerage)
        buy_charges = self.risk_engine.calculate_statutory_charges("BUY", price=1000.0, quantity=100)
        self.assertEqual(buy_charges["brokerage"], 0.0)
        self.assertEqual(buy_charges["stt"], 0.0)
        self.assertGreater(buy_charges["stamp_duty"], 0.0)

        # Test Sell side (STT 0.025% applied, zero brokerage)
        sell_charges = self.risk_engine.calculate_statutory_charges("SELL", price=1000.0, quantity=100)
        self.assertEqual(sell_charges["brokerage"], 0.0)
        self.assertEqual(sell_charges["stt"], 25.0) # 1,00,000 * 0.00025 = 25.0

    def test_technical_indicators(self):
        candles = [
            {"high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000.0},
            {"high": 104.0, "low": 100.0, "close": 103.0, "volume": 2000.0},
            {"high": 105.0, "low": 102.0, "close": 104.0, "volume": 1500.0}
        ]
        vwap = TechnicalIndicators.calculate_vwap(candles)
        self.assertEqual(len(vwap), 3)
        self.assertGreater(vwap[-1], 100.0)

        # Candlestick pattern detection: Shooting Star
        shooting_star = {"open": 100.0, "high": 110.0, "low": 99.5, "close": 101.0}
        pattern = TechnicalIndicators.detect_candle_pattern(shooting_star)
        self.assertEqual(pattern, "SHOOTING_STAR")

        # Candlestick pattern detection: Hammer
        hammer = {"open": 109.0, "high": 110.0, "low": 99.0, "close": 108.5}
        pattern_h = TechnicalIndicators.detect_candle_pattern(hammer)
        self.assertEqual(pattern_h, "HAMMER")

    def test_all_seven_strategies_eval(self):
        self.clock.set_simulated_time(datetime(2026, 11, 4, 9, 35))
        strats = [
            MomentumStrategy(),
            BreakoutStrategy(),
            ReversalStrategy(),
            VWAPStrategy(),
            ScalpingStrategy(),
            GapAndGoStrategy(),
            OpeningRangeBreakoutStrategy()
        ]
        # Verify each strategy can evaluate without raising any exceptions
        for s in strats:
            result = s.evaluate("RELIANCE", self.market_data, self.clock)
            self.assertTrue(result is None or isinstance(result, dict))

    def test_claude_tools_interface(self):
        tools = self.agent_interface.get_tool_definitions()
        self.assertEqual(len(tools), 10)

        # Execute get_market_clock_state tool
        self.clock.set_simulated_time(datetime(2026, 11, 4, 10, 0))
        clock_res = self.agent_interface.execute_tool("get_market_clock_state", {})
        self.assertEqual(clock_res["session_phase"], "MORNING_VOLATILITY")

        # Execute calculate_risk_and_size tool
        size_res = self.agent_interface.execute_tool("calculate_risk_and_size", {
            "symbol": "TATAMOTORS",
            "entry_price": 1000.0,
            "stop_loss": 990.0,
            "risk_pct": 0.015
        })
        self.assertEqual(size_res["quantity"], 150)

        # Place intraday order via tool
        order_res = self.agent_interface.execute_tool("place_intraday_order", {
            "symbol": "TATAMOTORS",
            "side": "BUY",
            "quantity": 50,
            "price": 1000.0,
            "stop_loss": 990.0,
            "target": 1020.0,
            "strategy": "momentum_trading",
            "rationale": "Test execution"
        })
        self.assertEqual(order_res["status"], "COMPLETE")

    def test_nse_collector_and_archive(self):
        from trading_harness.market_data.nse_live_collector import NSELiveCollector
        test_live_dir = "logs/test_live"
        test_archive_dir = "logs/test_archive"
        collector = NSELiveCollector(live_dir=test_live_dir, archive_dir=test_archive_dir)
        
        sample_records = [
            {
                "snapshot_ist": "2026-11-04 09:15:00",
                "symbol": "NIFTY 50",
                "is_index": True,
                "company_name": "NIFTY 50 INDEX",
                "last_price": 23950.0,
                "change": 50.0,
                "p_change": 0.25,
                "open": 23900.0,
                "day_high": 23960.0,
                "day_low": 23890.0,
                "prev_close": 23900.0,
                "volume": 1000000,
                "total_traded_value": 50000000.0,
                "year_high": 26000.0,
                "year_low": 22000.0,
                "nse_timestamp": "04-Nov-2026 09:15:00"
            }
        ]
        
        # Test appending to running file
        collector.append_to_running_file(sample_records)
        self.assertTrue(os.path.exists(collector.running_file_path))
        
        # Test archiving running file
        archived_path = collector.archive_running_file(target_date_str="2026-11-04")
        self.assertIsNotNone(archived_path)
        self.assertTrue(os.path.exists(archived_path))
        self.assertFalse(os.path.exists(collector.running_file_path))

if __name__ == "__main__":
    unittest.main()
