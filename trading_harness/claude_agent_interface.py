"""
Claude Agent Interface & Tool Schemas for Indian Intraday Trading.
Exposes standard Anthropic tool use definitions and execution dispatchers.
"""

from typing import Dict, Any, List, Optional
import json
import os
from .clock import IndianMarketClock
from .risk_engine import RiskEngine
from .broker.base import BaseBroker
from .market_data.feed import MarketDataFeed
from .journal import TradeJournal
from .indicators import TechnicalIndicators
from .strategies.momentum import MomentumStrategy
from .strategies.breakout import BreakoutStrategy
from .strategies.reversal import ReversalStrategy
from .strategies.vwap import VWAPStrategy
from .strategies.scalping import ScalpingStrategy
from .strategies.gap_and_go import GapAndGoStrategy
from .strategies.orb import OpeningRangeBreakoutStrategy

class ClaudeAgentInterface:
    def __init__(self, clock: IndianMarketClock, risk_engine: RiskEngine, 
                 broker: BaseBroker, market_data: MarketDataFeed, journal: TradeJournal):
        self.clock = clock
        self.risk_engine = risk_engine
        self.broker = broker
        self.market_data = market_data
        self.journal = journal
        
        self.strategies = {
            "momentum_trading": MomentumStrategy(),
            "breakout_trading": BreakoutStrategy(),
            "reversal_trading": ReversalStrategy(),
            "vwap_trading": VWAPStrategy(),
            "scalping": ScalpingStrategy(),
            "gap_and_go": GapAndGoStrategy(),
            "opening_range_breakout": OpeningRangeBreakoutStrategy()
        }

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Returns JSON Schemas for Claude's Function Calling / Tool Use API.
        """
        return [
            {
                "name": "get_market_clock_state",
                "description": "Returns current Indian Standard Time (IST), session phase, and auto-squareoff (15:20 IST) status.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_market_state",
                "description": "Retrieves real-time market data, VWAP, RSI, volume metrics, and Level 2 depth for an Indian symbol.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "NSE Symbol (e.g. RELIANCE, TATAMOTORS, SBIN, NIFTY_FUT)"}
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "scan_market_opportunities",
                "description": "Evaluates all 7 Flattrade intraday strategies across the active Indian market universe and returns actionable setups.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "strategy_filter": {
                            "type": "string", 
                            "description": "Optional: 'momentum_trading', 'breakout_trading', 'reversal_trading', 'vwap_trading', 'scalping', 'gap_and_go', 'opening_range_breakout'"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "calculate_risk_and_size",
                "description": "Calculates position sizing strictly adhering to the 1% to 2% max capital risk rule for Indian equities.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "entry_price": {"type": "number"},
                        "stop_loss": {"type": "number"},
                        "risk_pct": {"type": "number", "description": "Risk percentage between 0.005 and 0.02 (e.g. 0.015 for 1.5%)"}
                    },
                    "required": ["symbol", "entry_price", "stop_loss"]
                }
            },
            {
                "name": "place_intraday_order",
                "description": "Places an MIS intraday order with mandatory Stop-Loss and Target. Validated by RiskEngine before execution.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "side": {"type": "string", "enum": ["BUY", "SELL"]},
                        "quantity": {"type": "integer"},
                        "price": {"type": "number"},
                        "stop_loss": {"type": "number", "description": "Mandatory hard stop loss price"},
                        "target": {"type": "number", "description": "Profit target price"},
                        "strategy": {"type": "string"},
                        "rationale": {"type": "string", "description": "Detailed justification for trade"}
                    },
                    "required": ["symbol", "side", "quantity", "price", "stop_loss", "strategy", "rationale"]
                }
            },
            {
                "name": "get_open_positions",
                "description": "Returns all active open intraday positions and unrealized PnL.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "square_off_positions",
                "description": "Closes all open intraday positions immediately (used for 15:20 cut-off or daily drawdown kill-switch).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Reason for square-off (e.g. '15:20_CUTOFF', 'KILL_SWITCH', 'MANUAL')"}
                    },
                    "required": ["reason"]
                }
            },
            {
                "name": "get_trade_journal_summary",
                "description": "Returns End-Of-Day (EOD) trading review, net PnL after zero-brokerage statutory charges, and win-rate.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_nse_live_snapshot",
                "description": "Returns the latest real-time NIFTY 50 index and 50 constituent stocks snapshot collected from NSE website.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Optional: Specific constituent symbol (e.g. 'RELIANCE', 'HDFCBANK', 'NIFTY 50')"}
                    },
                    "required": []
                }
            },
            {
                "name": "archive_nse_running_file",
                "description": "Manually triggers End-Of-Day archiving of the running 3-minute NSE data file to data/archive/.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches Claude tool calls to the trading harness core"""
        try:
            if tool_name == "get_market_clock_state":
                return {
                    "current_ist": self.clock.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "session_phase": self.clock.get_session_phase(),
                    "is_market_open": self.clock.is_market_open(),
                    "is_square_off_time": self.clock.is_square_off_time(),
                    "kill_switch_active": self.risk_engine.daily_kill_switch_activated
                }

            elif tool_name == "get_market_state":
                sym = arguments["symbol"]
                ltp = self.market_data.get_ltp(sym)
                candles_5m = self.market_data.get_candles(sym, timeframe="5m", limit=20)
                closes = [c["close"] for c in candles_5m]
                rsi = TechnicalIndicators.calculate_rsi(closes, period=14)[-1] if len(closes) >= 15 else 50.0
                vwap = TechnicalIndicators.calculate_vwap(candles_5m)[-1] if candles_5m else ltp
                depth = self.market_data.get_market_depth(sym)
                
                highs = [c["high"] for c in candles_5m]
                lows = [c["low"] for c in candles_5m]

                return {
                    "symbol": sym,
                    "ltp": ltp,
                    "day_high": max(highs) if highs else ltp,
                    "day_low": min(lows) if lows else ltp,
                    "vwap": vwap,
                    "rsi_5m": rsi,
                    "spread": depth["spread"],
                    "bid_ask_depth_ratio": depth["bid_ask_ratio"]
                }

            elif tool_name == "scan_market_opportunities":
                strategy_filter = arguments.get("strategy_filter")
                opportunities = []
                universe = ["RELIANCE", "TATAMOTORS", "SBIN", "INFY", "HDFCBANK", "NIFTY_FUT"]
                
                for sym in universe:
                    for strat_name, strat in self.strategies.items():
                        if strategy_filter and strat_name != strategy_filter:
                            continue
                        signal = strat.evaluate(sym, self.market_data, self.clock)
                        if signal:
                            opportunities.append(signal)

                return {"count": len(opportunities), "opportunities": opportunities}

            elif tool_name == "calculate_risk_and_size":
                entry = float(arguments["entry_price"])
                sl = float(arguments["stop_loss"])
                risk_pct = float(arguments.get("risk_pct", 0.015))
                capital = self.broker.get_account_state()["capital"]
                qty = self.risk_engine.calculate_position_size(capital, entry, sl, risk_pct)
                risk_rupees = round(abs(entry - sl) * qty, 2)

                return {
                    "quantity": qty,
                    "risk_rupees": risk_rupees,
                    "capital": capital,
                    "risk_pct": risk_pct,
                    "per_share_risk": round(abs(entry - sl), 2)
                }

            elif tool_name == "place_intraday_order":
                order_payload = {
                    "symbol": arguments["symbol"],
                    "side": arguments["side"],
                    "product": "MIS",
                    "quantity": int(arguments["quantity"]),
                    "price": float(arguments["price"]),
                    "stop_loss": float(arguments["stop_loss"]),
                    "target": float(arguments.get("target", 0.0)),
                    "strategy": arguments["strategy"],
                    "rationale": arguments["rationale"]
                }
                res = self.broker.place_order(order_payload)
                return res

            elif tool_name == "get_open_positions":
                positions = self.broker.get_positions()
                account = self.broker.get_account_state()
                return {"positions": positions, "account_state": account}

            elif tool_name == "square_off_positions":
                reason = arguments.get("reason", "AGENT_TRIGGERED")
                res = self.broker.square_off_all(reason=reason)
                return {"status": "SUCCESS", "closed_positions": res}

            elif tool_name == "get_trade_journal_summary":
                return self.journal.get_eod_summary()

            elif tool_name == "get_nse_live_snapshot":
                from .market_data.nse_live_collector import NSELiveCollector
                collector = NSELiveCollector()
                sym = arguments.get("symbol")
                if os.path.exists(collector.latest_json_path):
                    with open(collector.latest_json_path, "r", encoding="utf-8") as jf:
                        latest = json.load(jf)
                    if sym:
                        sym_upper = sym.upper()
                        if sym_upper in ["NIFTY 50", "NIFTY"]:
                            return {"symbol": sym_upper, "data": latest.get("index")}
                        stock_data = latest.get("stocks", {}).get(sym_upper)
                        return {"symbol": sym_upper, "data": stock_data or "Not found"}
                    return latest
                else:
                    return {"status": "NO_SNAPSHOT", "message": "No live snapshot file found. Run run_nse_collector.py."}

            elif tool_name == "archive_nse_running_file":
                from .market_data.nse_live_collector import NSELiveCollector
                collector = NSELiveCollector()
                archived = collector.archive_running_file()
                return {"status": "SUCCESS" if archived else "NO_FILE", "archive_path": archived}

            else:
                return {"error": f"Unknown tool name: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}
