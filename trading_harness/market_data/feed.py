"""
Market Data Engine for Indian Intraday Trading.
Provides realistic OHLCV historical feeds, Level 2 depth books, pre-market gap generation,
and live streaming simulation for Indian equities and index derivatives.
"""

from typing import Dict, Any, List, Optional
import random
from datetime import datetime, timedelta

class MarketDataFeed:
    def __init__(self):
        # Default baseline prices for top liquid Indian symbols
        self.base_prices = {
            "RELIANCE": 2810.0,
            "TATAMOTORS": 980.0,
            "SBIN": 820.0,
            "INFY": 1500.0,
            "HDFCBANK": 1720.0,
            "NIFTY_FUT": 22420.0,
            "BANKNIFTY_FUT": 48500.0
        }
        self.active_candles: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._initialize_sample_data()

    def _initialize_sample_data(self):
        """Generates realistic baseline 1m, 5m, and 15m candles starting at 09:15 IST"""
        for symbol, base_px in self.base_prices.items():
            self.active_candles[symbol] = {
                "1m": self._generate_candles(symbol, base_px, count=60, timeframe_mins=1),
                "5m": self._generate_candles(symbol, base_px, count=25, timeframe_mins=5),
                "15m": self._generate_candles(symbol, base_px, count=12, timeframe_mins=15)
            }

    def _generate_candles(self, symbol: str, base_price: float, count: int, timeframe_mins: int) -> List[Dict[str, Any]]:
        candles = []
        curr_price = base_price
        start_time = datetime(2026, 11, 4, 9, 15)
        
        for i in range(count):
            candle_time = start_time + timedelta(minutes=i * timeframe_mins)
            # Volatility is higher in first 30 mins
            vol_mult = 1.8 if i < (30 // timeframe_mins) else 1.0
            
            delta_pct = (random.gauss(0.0003, 0.002)) * vol_mult
            o = curr_price
            c = round(o * (1 + delta_pct), 2)
            high_wiggle = abs(random.gauss(0, 0.0015)) * o
            low_wiggle = abs(random.gauss(0, 0.0015)) * o
            h = round(max(o, c) + high_wiggle, 2)
            l = round(min(o, c) - low_wiggle, 2)
            
            # Volume simulation (higher in morning)
            base_vol = 50000 if "FUT" not in symbol else 10000
            vol = int(base_vol * vol_mult * random.uniform(0.8, 2.5))
            
            candles.append({
                "timestamp": candle_time.strftime("%H:%M"),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": vol
            })
            curr_price = c
            
        return candles

    def get_candles(self, symbol: str, timeframe: str = "5m", limit: int = 20) -> List[Dict[str, Any]]:
        """Returns the most recent N candles for a symbol and timeframe"""
        if symbol not in self.active_candles:
            base_px = self.base_prices.get(symbol, 1000.0)
            mins = 1 if timeframe == "1m" else (15 if timeframe == "15m" else 5)
            self.active_candles[symbol] = {
                timeframe: self._generate_candles(symbol, base_px, count=limit, timeframe_mins=mins)
            }
        candles = self.active_candles[symbol].get(timeframe, [])
        return candles[-limit:]

    def get_market_depth(self, symbol: str) -> Dict[str, Any]:
        """
        Simulates Level 2 order book (top 5 bids and asks) and depth imbalance.
        """
        ltp = self.get_ltp(symbol)
        tick = 0.05
        
        bids = []
        asks = []
        total_bid_qty = 0
        total_ask_qty = 0
        
        for i in range(1, 6):
            b_px = round(ltp - (i * tick), 2)
            b_qty = random.randint(500, 4000)
            bids.append({"price": b_px, "quantity": b_qty, "orders": random.randint(2, 10)})
            total_bid_qty += b_qty
            
            a_px = round(ltp + (i * tick), 2)
            a_qty = random.randint(500, 4000)
            asks.append({"price": a_px, "quantity": a_qty, "orders": random.randint(2, 10)})
            total_ask_qty += a_qty
            
        ratio = round(total_bid_qty / total_ask_qty, 2) if total_ask_qty > 0 else 1.0
        
        return {
            "symbol": symbol,
            "ltp": ltp,
            "best_bid": bids[0]["price"],
            "best_ask": asks[0]["price"],
            "spread": round(asks[0]["price"] - bids[0]["price"], 2),
            "bids": bids,
            "asks": asks,
            "total_bid_qty": total_bid_qty,
            "total_ask_qty": total_ask_qty,
            "bid_ask_ratio": ratio
        }

    def get_ltp(self, symbol: str) -> float:
        candles = self.get_candles(symbol, timeframe="1m", limit=1)
        if candles:
            return candles[-1]["close"]
        return self.base_prices.get(symbol, 1000.0)

    def scan_premarket_gappers(self) -> List[Dict[str, Any]]:
        """
        Simulates pre-open market scan (09:00 - 09:08 IST).
        Returns top gappers with gap percentage and volume.
        """
        gappers = [
            {"symbol": "TATAMOTORS", "prev_close": 950.0, "open_price": 978.5, "gap_pct": 3.0, "catalyst": "Record quarterly EV sales"},
            {"symbol": "HDFCBANK", "prev_close": 1700.0, "open_price": 1735.0, "gap_pct": 2.06, "catalyst": "Strong Q2 net interest margin beat"},
            {"symbol": "INFY", "prev_close": 1520.0, "open_price": 1492.0, "gap_pct": -1.84, "catalyst": "Guidance revision lower"},
            {"symbol": "RELIANCE", "prev_close": 2805.0, "open_price": 2818.0, "gap_pct": 0.46, "catalyst": "Neutral retail update"}
        ]
        return gappers

    def load_live_nse_snapshot(self, path: str = "data/live/nifty50_latest.json") -> Optional[Dict[str, Any]]:
        """
        Loads the latest live NSE NIFTY 50 and constituent stocks snapshot
        collected by NSELiveCollector, updating active market feed prices.
        """
        import os
        import json
        if not os.path.exists(path):
            return None
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            stocks = data.get("stocks", {})
            for sym, sdata in stocks.items():
                ltp = float(sdata.get("last_price", 0.0))
                if ltp > 0:
                    self.base_prices[sym] = ltp
                    
            idx = data.get("index", {})
            if idx and "last_price" in idx:
                self.base_prices["NIFTY 50"] = float(idx["last_price"])
                self.base_prices["NIFTY_FUT"] = float(idx["last_price"])

            return data
        except Exception as e:
            print(f"[MarketDataFeed] Error loading live snapshot: {e}")
            return None
