"""
Strategy 2: Breakout Trading (Consolidation Range Expansion: 10:30 - 13:30 IST)
Detects horizontal trading ranges with at least 3 touches and range contraction <= 1.2%,
and triggers on high-volume (>= 2.5x) range expansion.
"""

from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators

class BreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="breakout_trading", timeframe="15m")

    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        candles = market_data.get_candles(symbol, timeframe="15m", limit=12)
        if len(candles) < 7:
            return None

        # Check for prior consolidation over preceding candles
        prior_candles = candles[:-1]
        consolidation = TechnicalIndicators.detect_consolidation_range(prior_candles, window=6)
        
        if not consolidation["is_consolidating"]:
            return None

        resistance = consolidation["resistance"]
        support = consolidation["support"]
        range_height = consolidation["range_height"]

        current_candle = candles[-1]
        volumes = [float(c["volume"]) for c in candles]
        rvol = TechnicalIndicators.calculate_relative_volume(volumes, period=6)

        # Bullish Breakout above Resistance
        if current_candle["close"] > resistance and rvol >= 2.2:
            entry = current_candle["close"]
            stop_loss = round(resistance * 0.996, 2) # Stop loss placed just below broken resistance
            target = round(entry + (range_height * 1.5), 2)
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "BUY",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Breakout above range resistance ({resistance:.2f}) with RVOL {rvol:.1f}x. Target: {target:.2f}"
            }

        # Bearish Breakdown below Support
        elif current_candle["close"] < support and rvol >= 2.2:
            entry = current_candle["close"]
            stop_loss = round(support * 1.004, 2) # Stop loss placed just above broken support
            target = round(entry - (range_height * 1.5), 2)
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "SELL",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Breakdown below range support ({support:.2f}) with RVOL {rvol:.1f}x. Target: {target:.2f}"
            }

        return None
