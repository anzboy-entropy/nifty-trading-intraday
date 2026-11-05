"""
Strategy 3: Reversal Trading / Mean Reversion
Identifies overextended intraday price surges/plummets with extreme RSI (>= 80 or <= 20),
candle exhaustion wicks (Shooting Star, Hammer, Engulfing), and targets reversion to VWAP.
"""

from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators

class ReversalStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="reversal_trading", timeframe="5m")

    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        candles = market_data.get_candles(symbol, timeframe="5m", limit=20)
        if len(candles) < 15:
            return None

        closes = [c["close"] for c in candles]
        rsi_list = TechnicalIndicators.calculate_rsi(closes, period=14)
        current_rsi = rsi_list[-1]
        
        vwap_list = TechnicalIndicators.calculate_vwap(candles)
        current_vwap = vwap_list[-1]

        current_candle = candles[-1]
        prev_candle = candles[-2]
        pattern = TechnicalIndicators.detect_candle_pattern(current_candle, prev_candle)
        ltp = current_candle["close"]

        # Bearish Reversal (Fading Parabolic Overbought Surge)
        # Condition: RSI >= 78, price well above VWAP (>= 1.5%), Shooting Star or Bearish Engulfing pattern
        if current_rsi >= 78.0 and ltp > (current_vwap * 1.015):
            if pattern in ["SHOOTING_STAR", "BEARISH_ENGULFING"]:
                entry = ltp
                swing_high = max(current_candle["high"], prev_candle["high"])
                stop_loss = round(swing_high * 1.002, 2) # Tight stop above exhaustion high
                target = current_vwap # Mean reversion target
                
                # Check R:R is at least 1:1.5
                if (entry - target) >= 1.5 * (stop_loss - entry):
                    return {
                        "strategy": self.name,
                        "symbol": symbol,
                        "side": "SELL",
                        "entry_price": entry,
                        "stop_loss": stop_loss,
                        "target": target,
                        "product": "MIS",
                        "rationale": f"Bearish Reversal: Overbought RSI {current_rsi:.1f}, {pattern} pattern, Target VWAP {current_vwap:.2f}"
                    }

        # Bullish Reversal (Fading Flash Oversold Drop)
        # Condition: RSI <= 22, price well below VWAP (<= 0.985), Hammer or Bullish Engulfing pattern
        elif current_rsi <= 22.0 and ltp < (current_vwap * 0.985):
            if pattern in ["HAMMER", "BULLISH_ENGULFING"]:
                entry = ltp
                swing_low = min(current_candle["low"], prev_candle["low"])
                stop_loss = round(swing_low * 0.998, 2) # Tight stop below exhaustion low
                target = current_vwap
                
                if (target - entry) >= 1.5 * (entry - stop_loss):
                    return {
                        "strategy": self.name,
                        "symbol": symbol,
                        "side": "BUY",
                        "entry_price": entry,
                        "stop_loss": stop_loss,
                        "target": target,
                        "product": "MIS",
                        "rationale": f"Bullish Reversal: Oversold RSI {current_rsi:.1f}, {pattern} pattern, Target VWAP {current_vwap:.2f}"
                    }

        return None
