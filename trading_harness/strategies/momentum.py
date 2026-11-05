"""
Strategy 1: Momentum Trading (Morning Volatility Window: 09:15 - 10:15 IST)
Rides strong directional moves in Indian equities when RSI > 60 (or < 40)
and volume surge > 2x average, with strict 0.5% - 1.0% stop-losses.
"""

from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators

class MomentumStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="momentum_trading", timeframe="5m")

    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        # Check active session phase
        phase = clock.get_session_phase()
        if phase not in ["MORNING_VOLATILITY", "PRIMARY_BREAKOUT"]:
            return None # Skip outside morning volatility window

        candles = market_data.get_candles(symbol, timeframe="5m", limit=25)
        if len(candles) < 15:
            return None

        closes = [c["close"] for c in candles]
        volumes = [float(c["volume"]) for c in candles]
        
        rsi_list = TechnicalIndicators.calculate_rsi(closes, period=14)
        current_rsi = rsi_list[-1]
        
        vwap_list = TechnicalIndicators.calculate_vwap(candles)
        current_vwap = vwap_list[-1]
        
        rvol = TechnicalIndicators.calculate_relative_volume(volumes, period=10)
        
        current_candle = candles[-1]
        prev_candle = candles[-2]
        ltp = current_candle["close"]

        # Bullish Momentum Setup
        if (ltp > current_vwap and 
            current_rsi >= 60.0 and 
            rvol >= 1.8 and 
            current_candle["close"] > prev_candle["high"]):
            
            entry = ltp
            stop_loss = round(entry * 0.992, 2) # 0.8% stop loss
            risk = entry - stop_loss
            target = round(entry + (risk * 2.0), 2)
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "BUY",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Bullish momentum: RSI {current_rsi:.1f} > 60, RVOL {rvol:.1f}x, Price above VWAP ({current_vwap:.2f})"
            }

        # Bearish Momentum Setup (Short Sell)
        elif (ltp < current_vwap and 
              current_rsi <= 40.0 and 
              rvol >= 1.8 and 
              current_candle["close"] < prev_candle["low"]):
              
            entry = ltp
            stop_loss = round(entry * 1.008, 2) # 0.8% stop loss
            risk = stop_loss - entry
            target = round(entry - (risk * 2.0), 2)
            
            return {
                "strategy": self.name,
                "symbol": symbol,
                "side": "SELL",
                "entry_price": entry,
                "stop_loss": stop_loss,
                "target": target,
                "product": "MIS",
                "rationale": f"Bearish momentum: RSI {current_rsi:.1f} < 40, RVOL {rvol:.1f}x, Price below VWAP ({current_vwap:.2f})"
            }

        return None
