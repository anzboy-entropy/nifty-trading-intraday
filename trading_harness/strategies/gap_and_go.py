"""
Strategy 6: Gap and Go (Pre-Market Gap Continuation: 09:15 - 10:15 IST)
Identifies overnight gaps >= 1.5%, confirms morning buyer/seller acceptance on the first 5m candle,
and trades aggressive continuation with the gap, invalidating immediately on gap fill.
"""

from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators

class GapAndGoStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="gap_and_go", timeframe="5m")

    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        # Gapper check
        gappers = market_data.scan_premarket_gappers()
        matched = next((g for g in gappers if g["symbol"] == symbol), None)
        if not matched:
            return None

        gap_pct = matched["gap_pct"]
        if abs(gap_pct) < 1.5 or abs(gap_pct) > 5.0:
            return None # Must be a clean, tradeable gap

        candles_5m = market_data.get_candles(symbol, timeframe="5m", limit=10)
        if len(candles_5m) < 2:
            return None

        first_candle = candles_5m[0] # Opening 09:15 - 09:20 candle
        current_candle = candles_5m[-1]
        ltp = current_candle["close"]

        # Bullish Gap and Go
        if gap_pct > 0:
            # First candle must have closed green and held above opening price
            if first_candle["close"] >= first_candle["open"]:
                if ltp > first_candle["high"]:
                    entry = ltp
                    stop_loss = first_candle["low"] # Gap-fill invalidation line
                    
                    # Ensure risk is reasonable (<= 1.2%)
                    if (entry - stop_loss) / entry <= 0.012:
                        target = round(entry + ((entry - stop_loss) * 2.0), 2)
                        return {
                            "strategy": self.name,
                            "symbol": symbol,
                            "side": "BUY",
                            "entry_price": entry,
                            "stop_loss": stop_loss,
                            "target": target,
                            "product": "MIS",
                            "rationale": f"Bullish Gap & Go: +{gap_pct:.2f}% overnight gap held, 5m candle high ({first_candle['high']:.2f}) broken"
                        }

        # Bearish Gap and Go (Gap Down)
        elif gap_pct < 0:
            if first_candle["close"] <= first_candle["open"]:
                if ltp < first_candle["low"]:
                    entry = ltp
                    stop_loss = first_candle["high"]
                    
                    if (stop_loss - entry) / entry <= 0.012:
                        target = round(entry - ((stop_loss - entry) * 2.0), 2)
                        return {
                            "strategy": self.name,
                            "symbol": symbol,
                            "side": "SELL",
                            "entry_price": entry,
                            "stop_loss": stop_loss,
                            "target": target,
                            "product": "MIS",
                            "rationale": f"Bearish Gap & Go: {gap_pct:.2f}% gap down held, 5m candle low ({first_candle['low']:.2f}) broken"
                        }

        return None
