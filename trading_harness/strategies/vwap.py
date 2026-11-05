"""
Strategy 4: VWAP Trading (Pullback Bounce & Fair Value Benchmark: 10:15 - 14:30 IST)
Trades low-volume pullbacks to VWAP that print clean rejection/bounce candles,
with stop-losses anchored 0.3% - 0.5% beyond the VWAP benchmark.
"""

from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators

class VWAPStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="vwap_trading", timeframe="5m")

    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        candles = market_data.get_candles(symbol, timeframe="5m", limit=25)
        if len(candles) < 15:
            return None

        vwap_list = TechnicalIndicators.calculate_vwap(candles)
        current_vwap = vwap_list[-1]
        
        current_candle = candles[-1]
        prev_candle = candles[-2]
        
        ltp = current_candle["close"]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        day_high = max(highs)
        day_low = min(lows)

        # Bullish VWAP Pullback Bounce
        # Condition: Overall trend is higher, candle dipped to touch VWAP (low <= vwap * 1.001) and closed above VWAP
        if (day_high > current_vwap * 1.008 and 
            current_candle["low"] <= current_vwap * 1.0015 and 
            current_candle["close"] > current_vwap and 
            current_candle["close"] > current_candle["open"]):
            
            entry = current_candle["close"]
            stop_loss = round(current_vwap * 0.996, 2) # 0.4% below VWAP
            target = day_high
            
            if (target - entry) >= 1.5 * (entry - stop_loss):
                return {
                    "strategy": self.name,
                    "symbol": symbol,
                    "side": "BUY",
                    "entry_price": entry,
                    "stop_loss": stop_loss,
                    "target": target,
                    "product": "MIS",
                    "rationale": f"Bullish VWAP Bounce: Low touched VWAP ({current_vwap:.2f}), closed strong at {entry:.2f}. Target Day High ({day_high:.2f})"
                }

        # Bearish VWAP Rejection (Short)
        # Condition: Overall trend is lower, candle rallied to test VWAP (high >= vwap * 0.9985) and closed below VWAP
        elif (day_low < current_vwap * 0.992 and 
              current_candle["high"] >= current_vwap * 0.9985 and 
              current_candle["close"] < current_vwap and 
              current_candle["close"] < current_candle["open"]):
              
            entry = current_candle["close"]
            stop_loss = round(current_vwap * 1.004, 2) # 0.4% above VWAP
            target = day_low
            
            if (entry - target) >= 1.5 * (stop_loss - entry):
                return {
                    "strategy": self.name,
                    "symbol": symbol,
                    "side": "SELL",
                    "entry_price": entry,
                    "stop_loss": stop_loss,
                    "target": target,
                    "product": "MIS",
                    "rationale": f"Bearish VWAP Rejection: High tested VWAP ({current_vwap:.2f}), rejected downwards at {entry:.2f}. Target Day Low ({day_low:.2f})"
                }

        return None
