"""
Strategy 5: Scalping (1-Minute Micro Execution for High-Liquidity Stocks & Derivatives)
Trades rapid price surges on 1m candles supported by Level 2 order book imbalances,
targeting ₹1.50 - ₹4.00 per share with ₹1.00 - ₹1.50 stop-losses.
"""

from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators

class ScalpingStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="scalping", timeframe="1m")

    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        # Scalping requires liquid conditions
        depth = market_data.get_market_depth(symbol)
        spread = depth["spread"]
        
        # Enforce tight spread rule (max 0.10 INR for liquid equities)
        if spread > 0.10:
            return None

        candles = market_data.get_candles(symbol, timeframe="1m", limit=15)
        if len(candles) < 8:
            return None

        closes = [c["close"] for c in candles]
        ema9 = TechnicalIndicators.calculate_ema(closes, period=9)[-1]
        
        current_candle = candles[-1]
        recent_highs = [c["high"] for c in candles[-5:-1]]
        recent_lows = [c["low"] for c in candles[-5:-1]]
        micro_high = max(recent_highs)
        micro_low = min(recent_lows)

        # Bullish Micro Scalp Setup
        # Condition: Depth ratio >= 1.6 (heavy buyers), price > 9 EMA, 1m candle breaks micro high
        if depth["bid_ask_ratio"] >= 1.6 and current_candle["close"] > ema9 and current_candle["close"] > micro_high:
            entry = depth["best_ask"]
            stop_loss = round(entry - 1.50, 2) # Fixed tight ₹1.50 stop
            target = round(entry + 3.00, 2)    # Quick ₹3.00 capture
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "BUY",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Micro Long Scalp: Depth Ratio {depth['bid_ask_ratio']:.2f}, 1m break above micro high {micro_high:.2f}, tight spread ₹{spread:.2f}"
            }

        # Bearish Micro Scalp Setup (Short)
        # Condition: Depth ratio <= 0.60 (heavy sellers), price < 9 EMA, 1m candle breaks micro low
        elif depth["bid_ask_ratio"] <= 0.60 and current_candle["close"] < ema9 and current_candle["close"] < micro_low:
            entry = depth["best_bid"]
            stop_loss = round(entry + 1.50, 2)
            target = round(entry - 3.00, 2)
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "SELL",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Micro Short Scalp: Depth Ratio {depth['bid_ask_ratio']:.2f}, 1m break below micro low {micro_low:.2f}, tight spread ₹{spread:.2f}"
            }

        return None
