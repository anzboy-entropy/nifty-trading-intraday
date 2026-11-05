"""
Real-time Intraday Scanner & Time Series Engine for Streamlit.
Analyzes NIFTY 50 and constituent-stock snapshots, computes technical indicators,
and probes for valid setups across the enabled intraday strategies.
"""

import os
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

from .indicators import TechnicalIndicators
from .risk_engine import RiskEngine
from .config import RiskConfig, StatutoryFeeStructure
from .clock import IndianMarketClock
from .strategies.supply_demand import SupplyDemandStrategy

class LiveScannerEngine:
    def __init__(self, capital: float = 100000.0, risk_pct: float = 0.015):
        self.capital = capital
        self.risk_pct = risk_pct
        self.clock = IndianMarketClock()
        self.risk_engine = RiskEngine(
            RiskConfig(account_capital=capital, risk_per_trade_pct=risk_pct),
            StatutoryFeeStructure(),
            self.clock
        )
    def load_running_data(self, file_path: str = "data/live/nifty50_running.csv") -> pd.DataFrame:
        if not os.path.exists(file_path):
            return pd.DataFrame()
        try:
            df = pd.read_csv(file_path)
            return df
        except Exception:
            return pd.DataFrame()

    def get_symbol_time_series(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Extracts observed NSE snapshots for the symbol.
        Synthetic chart bars are built separately and are never scanner input.
        """
        sym_df = df[df["symbol"] == symbol].copy()
        if len(sym_df) < 3:
            return pd.DataFrame()

        sym_df["timestamp"] = sym_df["snapshot_ist"]
        sym_df["close"] = sym_df["last_price"]
        sym_df["high"] = sym_df["day_high"]
        sym_df["low"] = sym_df["day_low"]
        sym_df = sym_df.sort_values("snapshot_ist").reset_index(drop=True)
        enriched = self._enrich_indicators(sym_df)
        enriched.attrs["data_source"] = "nse_daily_snapshots"
        enriched.attrs["timeframe"] = None
        return enriched

    def _enrich_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enriches the time series with VWAP, RSI-14, ATR, and EMAs.
        """
        candles = df.to_dict("records")
        
        # VWAP
        df["vwap"] = TechnicalIndicators.calculate_vwap(candles)
        
        # RSI 14
        closes = df["close"].tolist()
        df["rsi"] = TechnicalIndicators.calculate_rsi(closes, period=14)
        
        # ATR 14
        df["atr"] = TechnicalIndicators.calculate_atr(candles, period=14)
        
        # 9 EMA & 21 EMA
        df["ema9"] = TechnicalIndicators.calculate_ema(closes, period=9)
        df["ema21"] = TechnicalIndicators.calculate_ema(closes, period=21)
        
        # RVOL
        volumes = [float(v) for v in df["volume"].tolist()]
        rvol_list = []
        for i in range(len(volumes)):
            sub_vols = volumes[:i + 1]
            rvol_list.append(TechnicalIndicators.calculate_relative_volume(sub_vols, period=10))
        df["rvol"] = rvol_list

        return df

    def scan_symbol_setups(
        self,
        df_series: pd.DataFrame,
        symbol: str,
        active_strategies: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Probes the time series for enabled strategies and returns triggered setups.
        """
        if df_series.empty or len(df_series) < 15:
            return []

        if active_strategies is None:
            active_strategies = [
                "Momentum Trading", "Breakout Trading", "Reversal Trading",
                "VWAP Trading", "Scalping", "Gap and Go", "Opening Range Breakout",
                "Supply & Demand (5m)",
            ]

        setups = []
        last_row = df_series.iloc[-1]
        prev_row = df_series.iloc[-2]
        candles = df_series.to_dict("records")

        ltp = float(last_row["close"])
        vwap = float(last_row["vwap"])
        rsi = float(last_row["rsi"])
        rvol = float(last_row["rvol"])
        ema9 = float(last_row["ema9"])
        atr = float(last_row["atr"])
        day_high = float(df_series["high"].max())
        day_low = float(df_series["low"].min())
        prev_close = float(last_row.get("prev_close", ltp))

        # -------------------------------------------------------------
        # 1. Momentum Trading
        # -------------------------------------------------------------
        if "Momentum Trading" in active_strategies:
            # Bullish Momentum
            if ltp > vwap and rsi >= 60.0 and rvol >= 1.6 and ltp > prev_row["high"]:
                entry = ltp
                sl = round(entry * 0.992, 2) # 0.8% stop
                risk = entry - sl
                target = round(entry + (risk * 2.0), 2)
                size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                if size > 0:
                    setups.append(self._create_setup_dict(
                        strategy="Momentum Trading",
                        symbol=symbol,
                        side="BUY",
                        entry=entry,
                        stop_loss=sl,
                        target=target,
                        quantity=size,
                        confidence="HIGH" if rvol >= 2.0 else "MEDIUM",
                        rationale=f"Bullish momentum surge: 3m RSI ({rsi:.1f}) > 60, RVOL {rvol:.1f}x, Price strictly above VWAP ({vwap:.2f})"
                    ))
            # Bearish Momentum
            elif ltp < vwap and rsi <= 40.0 and rvol >= 1.6 and ltp < prev_row["low"]:
                entry = ltp
                sl = round(entry * 1.008, 2)
                risk = sl - entry
                target = round(entry - (risk * 2.0), 2)
                size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                if size > 0:
                    setups.append(self._create_setup_dict(
                        strategy="Momentum Trading",
                        symbol=symbol,
                        side="SELL",
                        entry=entry,
                        stop_loss=sl,
                        target=target,
                        quantity=size,
                        confidence="HIGH" if rvol >= 2.0 else "MEDIUM",
                        rationale=f"Bearish momentum breakdown: 3m RSI ({rsi:.1f}) < 40, RVOL {rvol:.1f}x, Price below VWAP ({vwap:.2f})"
                    ))

        # -------------------------------------------------------------
        # 2. Breakout Trading (Consolidation Channel Expansion)
        # -------------------------------------------------------------
        if "Breakout Trading" in active_strategies:
            consolidation = TechnicalIndicators.detect_consolidation_range(candles[-10:], window=6)
            if consolidation["is_consolidating"]:
                res = consolidation["resistance"]
                sup = consolidation["support"]
                range_h = consolidation["range_height"]

                if ltp > res and rvol >= 1.8:
                    entry = ltp
                    sl = round(res * 0.996, 2)
                    target = round(entry + (range_h * 1.5), 2)
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="Breakout Trading",
                            symbol=symbol,
                            side="BUY",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="HIGH",
                            rationale=f"Range Breakout: Closed above horizontal resistance ({res:.2f}) with RVOL {rvol:.1f}x (Range: {consolidation['range_pct']}%)"
                        ))
                elif ltp < sup and rvol >= 1.8:
                    entry = ltp
                    sl = round(sup * 1.004, 2)
                    target = round(entry - (range_h * 1.5), 2)
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="Breakout Trading",
                            symbol=symbol,
                            side="SELL",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="HIGH",
                            rationale=f"Range Breakdown: Sliced below support ({sup:.2f}) with RVOL {rvol:.1f}x"
                        ))

        # -------------------------------------------------------------
        # 3. Reversal Trading (Mean Reversion)
        # -------------------------------------------------------------
        if "Reversal Trading" in active_strategies:
            pattern = TechnicalIndicators.detect_candle_pattern(candles[-1], candles[-2])
            # Overbought fade
            if rsi >= 75.0 and ltp > (vwap * 1.012) and pattern in ["SHOOTING_STAR", "BEARISH_ENGULFING", "DOJI"]:
                entry = ltp
                sl = round(max(last_row["high"], prev_row["high"]) * 1.002, 2)
                target = vwap
                if (entry - target) >= 1.5 * (sl - entry):
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, 0.01) # 1% cap for counter-trend
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="Reversal Trading",
                            symbol=symbol,
                            side="SELL",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="MEDIUM",
                            rationale=f"Overbought Exhaustion Reversal: RSI {rsi:.1f} >= 75, {pattern} pattern, stretched from VWAP ({vwap:.2f})"
                        ))
            # Oversold fade
            elif rsi <= 25.0 and ltp < (vwap * 0.988) and pattern in ["HAMMER", "BULLISH_ENGULFING", "DOJI"]:
                entry = ltp
                sl = round(min(last_row["low"], prev_row["low"]) * 0.998, 2)
                target = vwap
                if (target - entry) >= 1.5 * (entry - sl):
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, 0.01)
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="Reversal Trading",
                            symbol=symbol,
                            side="BUY",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="MEDIUM",
                            rationale=f"Oversold Bounce Reversal: RSI {rsi:.1f} <= 25, {pattern} pattern, target fair-value VWAP ({vwap:.2f})"
                        ))

        # -------------------------------------------------------------
        # 4. VWAP Pullback Bounce
        # -------------------------------------------------------------
        if "VWAP Trading" in active_strategies:
            # Bullish bounce: dipped near VWAP and closed green above VWAP
            if (day_high > vwap * 1.006 and 
                last_row["low"] <= vwap * 1.002 and 
                ltp > vwap and 
                last_row["close"] >= last_row["open"]):
                
                entry = ltp
                sl = round(vwap * 0.996, 2)
                target = day_high
                if (target - entry) >= 1.4 * (entry - sl):
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="VWAP Trading",
                            symbol=symbol,
                            side="BUY",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="HIGH",
                            rationale=f"Institutional VWAP Pullback Bounce: Low touched VWAP ({vwap:.2f}), bounced upward targeting Day High ({day_high:.2f})"
                        ))

        # -------------------------------------------------------------
        # 5. Scalping (Micro 9-EMA Momentum)
        # -------------------------------------------------------------
        if "Scalping" in active_strategies:
            if ltp > ema9 and ltp > prev_row["high"] and rsi > 55.0 and rsi < 70.0:
                entry = ltp
                sl = round(entry - 1.50, 2) # Micro tick stop
                target = round(entry + 3.00, 2) # Quick micro target
                size = min(300, int(1000.0 / 1.50)) # Fixed 1000 INR risk scalp
                setups.append(self._create_setup_dict(
                    strategy="Scalping",
                    symbol=symbol,
                    side="BUY",
                    entry=entry,
                    stop_loss=sl,
                    target=target,
                    quantity=size,
                    confidence="MEDIUM",
                    rationale=f"1m/3m Micro Scalp: Price above 9 EMA ({ema9:.2f}), rapid momentum thrust, 1:2 R:R micro target"
                ))

        # -------------------------------------------------------------
        # 6. Gap and Go
        # -------------------------------------------------------------
        if "Gap and Go" in active_strategies and prev_close > 0:
            open_px = float(df_series.iloc[0]["open"])
            gap_pct = ((open_px - prev_close) / prev_close) * 100.0
            first_candle = candles[0]
            
            # Gap Up Continuation
            if gap_pct >= 1.2 and ltp > first_candle["high"]:
                entry = ltp
                sl = first_candle["low"]
                if (entry - sl) / entry <= 0.012: # Within 1.2% risk
                    target = round(entry + ((entry - sl) * 2.0), 2)
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="Gap and Go",
                            symbol=symbol,
                            side="BUY",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="HIGH",
                            rationale=f"Overnight Gap & Go: +{gap_pct:.2f}% gap held, broke opening candle high ({first_candle['high']:.2f})"
                        ))

        # -------------------------------------------------------------
        # 7. Opening Range Breakout (ORB)
        # -------------------------------------------------------------
        if "Opening Range Breakout" in active_strategies and len(candles) >= 5:
            # First 5 3-minute candles = 15-minute Opening Range (09:15 - 09:30)
            or_candles = candles[:5]
            orh = max(c["high"] for c in or_candles)
            orl = min(c["low"] for c in or_candles)
            or_size = orh - orl
            midpoint = round((orh + orl) / 2.0, 2)

            if or_size <= (atr * 1.3) and or_size > 0:
                if ltp > orh and ltp > vwap:
                    entry = ltp
                    sl = midpoint
                    target = round(entry + (or_size * 1.5), 2)
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="Opening Range Breakout",
                            symbol=symbol,
                            side="BUY",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="HIGH",
                            rationale=f"15m ORB Breakout: Broke ORH ({orh:.2f}) with Range Size {or_size:.2f}. Midpoint SL {midpoint:.2f}, Target {target:.2f}"
                        ))
                elif ltp < orl and ltp < vwap:
                    entry = ltp
                    sl = midpoint
                    target = round(entry - (or_size * 1.5), 2)
                    size = self.risk_engine.calculate_position_size(self.capital, entry, sl, self.risk_pct)
                    if size > 0:
                        setups.append(self._create_setup_dict(
                            strategy="Opening Range Breakout",
                            symbol=symbol,
                            side="SELL",
                            entry=entry,
                            stop_loss=sl,
                            target=target,
                            quantity=size,
                            confidence="HIGH",
                            rationale=f"15m ORB Breakdown: Sliced below ORL ({orl:.2f}) with Range Size {or_size:.2f}. Target {target:.2f}"
                        ))

        # -------------------------------------------------------------
        # 8. Supply and Demand (verified or explicitly permitted estimated 5m OHLCV)
        # -------------------------------------------------------------
        if "Supply & Demand (5m)" in active_strategies:
            signal = SupplyDemandStrategy().evaluate(df_series)
            if signal:
                size = self.risk_engine.calculate_position_size(
                    self.capital,
                    signal["entry"],
                    signal["stop_loss"],
                    self.risk_pct,
                )
                if size > 0:
                    setup = self._create_setup_dict(
                        strategy=signal["strategy"],
                        symbol=symbol,
                        side=signal["side"],
                        entry=signal["entry"],
                        stop_loss=signal["stop_loss"],
                        target=signal["target"],
                        quantity=size,
                        confidence=signal["confidence"],
                        rationale=signal["rationale"],
                    )
                    setup["data_quality"] = signal["data_quality"]
                    setups.append(setup)

        return setups

    def _create_setup_dict(self, strategy: str, symbol: str, side: str, 
                           entry: float, stop_loss: float, target: float, 
                           quantity: int, confidence: str, rationale: str) -> Dict[str, Any]:
        risk_per_share = abs(entry - stop_loss)
        reward_per_share = abs(target - entry)
        rr_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else 0.0
        max_risk_rupees = round(risk_per_share * quantity, 2)
        potential_reward_rupees = round(reward_per_share * quantity, 2)

        return {
            "strategy": strategy,
            "symbol": symbol,
            "side": side,
            "entry_price": entry,
            "stop_loss": stop_loss,
            "target": target,
            "risk_reward": f"1:{rr_ratio}",
            "rr_numeric": rr_ratio,
            "quantity": quantity,
            "max_risk_inr": max_risk_rupees,
            "potential_reward_inr": potential_reward_rupees,
            "confidence": confidence,
            "rationale": rationale,
            "product": "MIS"
        }
