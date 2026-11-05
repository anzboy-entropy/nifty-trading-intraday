"""
Technical Indicators Engine for Indian Intraday Strategies.
Calculates VWAP, RSI, ATR, EMAs, Candle Patterns, Opening Range, and Consolidation detection.
"""

from typing import List, Dict, Any, Tuple, Optional
import math

class TechnicalIndicators:
    @staticmethod
    def calculate_vwap(candles: List[Dict[str, float]]) -> List[float]:
        """
        Calculates intraday Volume Weighted Average Price (VWAP).
        Each candle must have: 'high', 'low', 'close', 'volume'.
        Resets at the start of each intraday session.
        """
        vwap_values = []
        cum_volume = 0.0
        cum_vol_price = 0.0
        
        for c in candles:
            typical_price = (c['high'] + c['low'] + c['close']) / 3.0
            volume = float(c.get('volume', 0.0))
            
            cum_vol_price += typical_price * volume
            cum_volume += volume
            
            if cum_volume > 0:
                vwap_values.append(round(cum_vol_price / cum_volume, 2))
            else:
                vwap_values.append(typical_price)
                
        return vwap_values

    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> List[float]:
        """
        Calculates Relative Strength Index (RSI) using Wilder's Smoothing.
        """
        if len(closes) < period + 1:
            return [50.0] * len(closes)
        
        rsi_values = [50.0] * period
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(0.0, change))
            losses.append(max(0.0, -change))
            
        # First average
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(round(100.0 - (100.0 / (1.0 + rs)), 2))
            
        # Subsequent values
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(round(100.0 - (100.0 / (1.0 + rs)), 2))
                
        return rsi_values

    @staticmethod
    def calculate_atr(candles: List[Dict[str, float]], period: int = 14) -> List[float]:
        """
        Calculates Average True Range (ATR).
        """
        if len(candles) < 2:
            return [1.0] * len(candles)
        
        tr_list = []
        for i in range(len(candles)):
            if i == 0:
                tr_list.append(candles[i]['high'] - candles[i]['low'])
            else:
                h_l = candles[i]['high'] - candles[i]['low']
                h_pc = abs(candles[i]['high'] - candles[i - 1]['close'])
                l_pc = abs(candles[i]['low'] - candles[i - 1]['close'])
                tr_list.append(max(h_l, h_pc, l_pc))
                
        atr_values = []
        if len(tr_list) < period:
            return tr_list
            
        # Initial ATR
        current_atr = sum(tr_list[:period]) / period
        atr_values.extend([current_atr] * period)
        
        for tr in tr_list[period:]:
            current_atr = (current_atr * (period - 1) + tr) / period
            atr_values.append(round(current_atr, 2))
            
        return atr_values

    @staticmethod
    def calculate_ema(values: List[float], period: int) -> List[float]:
        """Calculates Exponential Moving Average (EMA)."""
        if not values:
            return []
        if len(values) < period:
            return values
            
        ema_values = []
        multiplier = 2.0 / (period + 1)
        
        # Simple moving average for the first point
        sma = sum(values[:period]) / period
        ema_values.extend([sma] * period)
        current_ema = sma
        
        for val in values[period:]:
            current_ema = (val - current_ema) * multiplier + current_ema
            ema_values.append(round(current_ema, 2))
            
        return ema_values

    @staticmethod
    def calculate_relative_volume(volumes: List[float], period: int = 20) -> float:
        """Computes RVOL (current candle volume / average volume of last N candles)."""
        if len(volumes) < 2:
            return 1.0
        current_vol = volumes[-1]
        prior_vols = volumes[-min(len(volumes), period + 1):-1]
        if not prior_vols:
            return 1.0
        avg_vol = sum(prior_vols) / len(prior_vols)
        if avg_vol == 0:
            return 1.0
        return round(current_vol / avg_vol, 2)

    @staticmethod
    def detect_candle_pattern(candle: Dict[str, float], prev_candle: Optional[Dict[str, float]] = None) -> str:
        """
        Detects key candlestick exhaustion and breakout patterns:
        - SHOOTING_STAR: Bearish exhaustion wick at top >= 2x body
        - HAMMER: Bullish exhaustion wick at bottom >= 2x body
        - BEARISH_ENGULFING: Red candle engulfing prior green candle
        - BULLISH_ENGULFING: Green candle engulfing prior red candle
        - DOJI: Body < 10% of total candle range
        - NORMAL: Standard candle
        """
        o = candle['open']
        h = candle['high']
        l = candle['low']
        c = candle['close']
        
        body = abs(c - o)
        candle_range = h - l
        
        if candle_range <= 0.0001:
            return "DOJI"
            
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        
        # Shooting Star: Upper wick >= 2x body, tiny lower wick, close in bottom 35% of candle
        if upper_wick >= 2 * max(body, 0.01) and lower_wick <= (candle_range * 0.15) and (c <= l + candle_range * 0.35):
            return "SHOOTING_STAR"
            
        # Hammer: Lower wick >= 2x body, tiny upper wick, close in upper 35% of candle
        if lower_wick >= 2 * max(body, 0.01) and upper_wick <= (candle_range * 0.15) and (c >= h - candle_range * 0.35):
            return "HAMMER"

        # Doji check: Body < 5% of total candle range and balanced wicks
        if body / candle_range < 0.05:
            return "DOJI"
            
        # Engulfing patterns
        if prev_candle is not None:
            prev_o = prev_candle['open']
            prev_c = prev_candle['close']
            prev_body = abs(prev_c - prev_o)
            
            # Bearish Engulfing
            if prev_c > prev_o and c < o: # Previous was green, current is red
                if o >= prev_c and c <= prev_o and body > prev_body:
                    return "BEARISH_ENGULFING"
                    
            # Bullish Engulfing
            if prev_c < prev_o and c > o: # Previous was red, current is green
                if o <= prev_c and c >= prev_o and body > prev_body:
                    return "BULLISH_ENGULFING"
                    
        return "NORMAL"

    @staticmethod
    def calculate_opening_range(candles_15m: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculates 15-minute Opening Range High, Low, and Size from the 09:15-09:30 candle.
        """
        if not candles_15m:
            return {"orh": 0.0, "orl": 0.0, "range_size": 0.0, "midpoint": 0.0}
            
        first_candle = candles_15m[0]
        orh = first_candle['high']
        orl = first_candle['low']
        range_size = round(orh - orl, 2)
        midpoint = round((orh + orl) / 2.0, 2)
        
        return {
            "orh": orh,
            "orl": orl,
            "range_size": range_size,
            "midpoint": midpoint
        }

    @staticmethod
    def detect_consolidation_range(candles_15m: List[Dict[str, float]], window: int = 6) -> Dict[str, Any]:
        """
        Identifies tight horizontal consolidation ranges over the last N 15m candles.
        Returns resistance, support, range height, and touch counts.
        """
        if len(candles_15m) < window:
            return {"is_consolidating": False, "resistance": 0.0, "support": 0.0, "touches": 0}
            
        recent = candles_15m[-window:]
        highs = [c['high'] for c in recent]
        lows = [c['low'] for c in recent]
        
        resistance = max(highs)
        support = min(lows)
        range_height = resistance - support
        mid_price = (resistance + support) / 2.0
        
        range_pct = (range_height / mid_price) * 100.0 if mid_price > 0 else 100.0
        
        # Count touches within 0.15% of resistance and support
        res_tolerance = resistance * 0.0015
        sup_tolerance = support * 0.0015
        
        res_touches = sum(1 for h in highs if abs(h - resistance) <= res_tolerance)
        sup_touches = sum(1 for l in lows if abs(l - support) <= sup_tolerance)
        total_touches = res_touches + sup_touches
        
        # Consolidation is valid if range is tight (<= 1.2%) and has at least 3 touches
        is_consolidating = (range_pct <= 1.2) and (res_touches >= 1) and (sup_touches >= 1) and (total_touches >= 3)
        
        return {
            "is_consolidating": is_consolidating,
            "resistance": resistance,
            "support": support,
            "range_height": round(range_height, 2),
            "range_pct": round(range_pct, 2),
            "touches": total_touches,
            "res_touches": res_touches,
            "sup_touches": sup_touches
        }
