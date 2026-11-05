"""
Indian Intraday Trading Harness Runner.
Simulates and coordinates agentic trading sessions, risk controls, order fills,
and trade journaling.
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any, List

from .config import TradingHarnessConfig
from .clock import IndianMarketClock
from .risk_engine import RiskEngine
from .broker.mock_broker import MockBroker
from .market_data.feed import MarketDataFeed
from .journal import TradeJournal
from .claude_agent_interface import ClaudeAgentInterface

class TradingHarness:
    def __init__(self, config: TradingHarnessConfig = None):
        self.config = config or TradingHarnessConfig()
        self.clock = IndianMarketClock(self.config.session)
        self.risk_engine = RiskEngine(self.config.risk, self.config.fees, self.clock)
        self.market_data = MarketDataFeed()
        self.broker = MockBroker(self.config.risk.account_capital, self.risk_engine, self.clock, market_data=self.market_data)
        self.journal = TradeJournal(self.config.journal_file)
        self.agent_interface = ClaudeAgentInterface(
            clock=self.clock,
            risk_engine=self.risk_engine,
            broker=self.broker,
            market_data=self.market_data,
            journal=self.journal
        )

    def run_simulated_session(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Executes a complete end-to-end simulated Indian intraday session:
        1. 09:15 AM - Morning Volatility & Momentum / Gap & Go scans
        2. 09:30 AM - Opening Range Breakout (ORB) calculation & triggers
        3. 11:30 AM - Midday Breakout & VWAP pullback opportunities
        4. 14:00 PM - Scalping & Reversal evaluation
        5. 15:20 PM - Mandatory MIS Square-Off Cut-off
        6. 15:30 PM - EOD Trade Journal & Performance Review
        """
        if verbose:
            print("=" * 80)
            print("[START] INDIAN INTRADAY TRADING HARNESS (AGENTIC CLAUDE MODE)")
            print(f"Capital: INR {self.config.risk.account_capital:,.2f} | Broker: {self.config.broker_type} (Zero Brokerage)")
            print(f"Risk Cap: {self.config.risk.risk_per_trade_pct * 100:.1f}% per trade | MIS Cut-off: {self.config.session.auto_square_off_time} IST")
            print("=" * 80)

        # 1. 09:18 IST - Morning Volatility Phase
        self.clock.set_simulated_time(datetime(2026, 11, 4, 9, 18))
        if verbose:
            print(f"\n[PHASE 1] {self.clock.current_time_str()} IST - {self.clock.get_session_phase()}")
            print("Scanning Pre-market Gaps & Morning Momentum...")
            
        gaps = self.market_data.scan_premarket_gappers()
        if verbose:
            print(f"Pre-open scan found {len(gaps)} gappers. Top pick: {gaps[0]['symbol']} ({gaps[0]['gap_pct']:+0.2f}%) - {gaps[0]['catalyst']}")

        # Simulate Gap & Go trade on TATAMOTORS
        tatamotors_entry = 985.0
        tatamotors_sl = 976.0 # Stop below 5m low
        tatamotors_tgt = round(tatamotors_entry + 2 * (tatamotors_entry - tatamotors_sl), 2)
        qty = self.risk_engine.calculate_position_size(self.broker.capital, tatamotors_entry, tatamotors_sl, 0.015)
        
        order1 = self.broker.place_order({
            "symbol": "TATAMOTORS",
            "side": "BUY",
            "quantity": qty,
            "price": tatamotors_entry,
            "stop_loss": tatamotors_sl,
            "target": tatamotors_tgt,
            "strategy": "gap_and_go",
            "product": "MIS"
        })
        if verbose:
            print(f"Executed Order 1: {order1['side']} {order1['quantity']} {order1['symbol']} @ INR {order1['price']} | SL: INR {order1['stop_loss']} | Tgt: INR {order1['target']} [Status: {order1['status']}]")

        # 2. 09:35 IST - Opening Range Breakout (ORB) on NIFTY_FUT
        self.clock.set_simulated_time(datetime(2026, 11, 4, 9, 35))
        if verbose:
            print(f"\n[PHASE 2] {self.clock.current_time_str()} IST - {self.clock.get_session_phase()}")
            print("Evaluating 15-minute Opening Range on NIFTY 50 Futures...")
            
        nifty_entry = 22460.0
        nifty_sl = 22425.0 # Midpoint of 22400-22450 range
        nifty_tgt = 22530.0 # 1.5x range
        nifty_qty = self.risk_engine.calculate_position_size(self.broker.capital, nifty_entry, nifty_sl, 0.015)
        
        order2 = self.broker.place_order({
            "symbol": "NIFTY_FUT",
            "side": "BUY",
            "quantity": nifty_qty,
            "price": nifty_entry,
            "stop_loss": nifty_sl,
            "target": nifty_tgt,
            "strategy": "opening_range_breakout",
            "product": "MIS"
        })
        if verbose:
            print(f"Executed Order 2: {order2['side']} {order2['quantity']} {order2['symbol']} @ INR {order2['price']} | SL: INR {order2['stop_loss']} | Tgt: INR {order2['target']} [Status: {order2['status']}]")

        # 3. 11:30 AM - Midday VWAP Bounce on INFY
        self.clock.set_simulated_time(datetime(2026, 11, 4, 11, 30))
        if verbose:
            print(f"\n[PHASE 3] {self.clock.current_time_str()} IST - {self.clock.get_session_phase()}")
            print("Monitoring VWAP Pullback Bounce on INFY...")
            
        infy_entry = 1492.0
        infy_sl = 1486.0 # 0.4% below VWAP
        infy_tgt = 1505.0 # Day High
        infy_qty = self.risk_engine.calculate_position_size(self.broker.capital, infy_entry, infy_sl, 0.015)
        
        order3 = self.broker.place_order({
            "symbol": "INFY",
            "side": "BUY",
            "quantity": infy_qty,
            "price": infy_entry,
            "stop_loss": infy_sl,
            "target": infy_tgt,
            "strategy": "vwap_trading",
            "product": "MIS"
        })
        if verbose:
            print(f"Executed Order 3: {order3['side']} {order3['quantity']} {order3['symbol']} @ INR {order3['price']} | SL: INR {order3['stop_loss']} | Tgt: INR {order3['target']} [Status: {order3['status']}]")

        # 4. Market Price Progression: Simulate Target hits
        if verbose:
            print("\n[SIMULATING INTRADAY PRICE ACTION]")
            
        # TATAMOTORS hits target
        self.broker.update_ltp("TATAMOTORS", tatamotors_tgt)
        if verbose:
            print(f"TATAMOTORS price reached INR {tatamotors_tgt} -> Target Hit! Position Closed.")

        # NIFTY_FUT hits target
        self.broker.update_ltp("NIFTY_FUT", nifty_tgt)
        if verbose:
            print(f"NIFTY_FUT price reached INR {nifty_tgt} -> Target Hit! Position Closed.")

        # 5. 15:20 IST - Mandatory Auto Square-off Cut-Off
        self.clock.set_simulated_time(datetime(2026, 11, 4, 15, 20))
        if verbose:
            print(f"\n[PHASE 4] {self.clock.current_time_str()} IST - {self.clock.get_session_phase()}")
            print("[CUT-OFF] 15:20 IST REACHED - Enforcing Mandatory MIS Auto Square-off for remaining open positions...")

        # Update remaining INFY price (modest profit)
        self.broker.update_ltp("INFY", 1498.0)
        closed_sq = self.broker.square_off_all(reason="15:20_MIS_AUTO_SQUAREOFF")
        for c in closed_sq:
            if verbose:
                print(f"Auto-Squared Off: {c['symbol']} @ INR {c['closed_price']} (Reason: {c['reason']})")

        # 6. Log trades into Trade Journal
        for ord_id, o in self.broker.orders.items():
            if o.get("reason") in ["TARGET_HIT", "STOP_LOSS_HIT", "15:20_MIS_AUTO_SQUAREOFF"]:
                self.journal.log_trade({
                    "trade_id": ord_id,
                    "symbol": o["symbol"],
                    "strategy": o.get("strategy", "intraday"),
                    "side": "BUY",
                    "quantity": o["quantity"],
                    "entry_price": o["price"] - (o["gross_pnl"] / o["quantity"]),
                    "exit_price": o["price"],
                    "stop_loss": 0.0,
                    "target": 0.0,
                    "statutory_charges": o["charges"]["total_charges"],
                    "exit_reason": o["reason"],
                    "rationale": "Automated simulated intraday execution"
                })

        # 7. Post-Market Performance Review
        eod_summary = self.journal.get_eod_summary()
        account_summary = self.broker.get_account_state()
        
        if verbose:
            print("\n" + "=" * 80)
            print("[EOD REPORT] END OF DAY TRADING PERFORMANCE SUMMARY")
            print("=" * 80)
            print(f"Total Completed Trades: {len(self.journal.trades)}")
            print(f"Gross Realized PnL:     INR {account_summary['realized_pnl']:+,.2f}")
            print(f"Total Statutory Charges: INR {account_summary['total_statutory_charges']:,.2f} (STT + Exchange + GST + Stamp Duty)")
            print(f"Net Realized PnL:       INR {(account_summary['realized_pnl'] - account_summary['total_statutory_charges']):+,.2f}")
            print(f"Win Rate:               {eod_summary['win_rate_pct']:.1f}%")
            print(f"Profit Factor:          {eod_summary['profit_factor']}")
            print("=" * 80)

        return {
            "account_state": account_summary,
            "eod_summary": eod_summary,
            "orders": self.broker.get_orders()
        }

if __name__ == "__main__":
    harness = TradingHarness()
    harness.run_simulated_session()
