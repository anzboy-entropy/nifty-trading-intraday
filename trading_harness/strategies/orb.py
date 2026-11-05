"""
Strategy 7: Opening Range Breakout (ORB: 09:30 - 11:00 IST)
Marks the 15-minute Opening Range (09:15 - 09:30 IST) high and low.
Filters out abnormally wide ranges (Range > 0.70x ATR), and trades breakouts with 1.5x-2x targets.
"""

from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators

class OpeningRangeBreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="opening_range_breakout", timeframe="15m")

    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        phase = clock.get_session_phase()
        if phase not in ["PRIMARY_BREAKOUT", "MORNING_VOLATILITY"]:
            return None

        candles_15m = market_data.get_candles(symbol, timeframe="15m", limit=8)
        if len(candles_15m) < 2:
            return None # Opening 15m candle must be fully closed

        opening_range = TechnicalIndicators.calculate_opening_range(candles_15m)
        orh = opening_range["orh"]
        orl = opening_range["orl"]
        range_size = opening_range["range_size"]
        midpoint = opening_range["midpoint"]

        if range_size <= 0:
            return None

        # Check ATR filter: Wide-range trap defense
        atr_list = TechnicalIndicators.calculate_atr(candles_15m, period=5)
        current_atr = atr_list[-1] if atr_list else (range_size * 1.5)
        
        # If Opening Range is abnormally wide (> 0.75x ATR), skip trade per Flattrade rule
        if range_size > (current_atr * 1.3):
            return None

        current_candle = candles_15m[-1]
        ltp = current_candle["close"]

        # Bullish ORB Breakout above ORH
        if ltp > orh:
            entry = ltp
            stop_loss = midpoint # Use Midpoint of range for optimal risk-reward
            target = round(entry + (range_size * 1.5), 2)
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "BUY",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Bullish 15m ORB: Broke ORH ({orh:.2f}) with Range Size {range_size:.2f}. Midpoint SL {midpoint:.2f}, Target {target:.2f}"
            }

        # Bearish ORB Breakdown below ORL
        elif ltp < orl:
            entry = ltp
            stop_loss = midpoint
            target = round(entry - (range_size * 1.5), 2)
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "SELL",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Bearish 15m ORB: Broke ORL ({orl:.2f}) with Range Size {range_size:.2f}. Midpoint SL {midpoint:.2f}, Target {target:.2f}"
            }

        return None
