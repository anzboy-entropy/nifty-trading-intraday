"""Supply-and-demand zone analysis for intraday OHLCV."""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..indicators import TechnicalIndicators


STRATEGY_NAME = "Supply & Demand (5m)"


class SupplyDemandStrategy:
    """Detect base/departure zones and first-touch retests in permitted data."""

    def evaluate(self, candles: pd.DataFrame) -> Optional[Dict[str, Any]]:
        validated = self._validated_session(candles)
        if validated is None:
            return None

        data, context = validated
        is_estimated = candles.attrs.get("data_source") == "synthetic_estimate"
        zones = self._find_zones(data)
        if not zones:
            return None

        current = data.iloc[-1]
        previous = data.iloc[-2]
        atr = self._atr(data)[-1]
        if atr <= 0:
            return None

        for zone in reversed(zones):
            lifecycle = self._zone_lifecycle(data, zone)
            if lifecycle["invalidated"] or not lifecycle["current_retest"]:
                continue

            if zone["type"] == "demand":
                confirms, evidence = self._bullish_confirmation(current, previous, zone)
                side = "BUY"
                stop = zone["low"] - atr * 0.1
                entry = float(current["high"]) + self._tick_size(candles)
                opposing = [
                    item for item in zones
                    if item["type"] == "supply"
                    and item["created"] < len(data) - 1
                    and not self._zone_lifecycle(data, item)["invalidated"]
                    and item["low"] > entry
                ]
                target = min((item["low"] for item in opposing), default=None)
            else:
                confirms, evidence = self._bearish_confirmation(current, previous, zone)
                side = "SELL"
                stop = zone["high"] + atr * 0.1
                entry = float(current["low"]) - self._tick_size(candles)
                opposing = [
                    item for item in zones
                    if item["type"] == "demand"
                    and item["created"] < len(data) - 1
                    and not self._zone_lifecycle(data, item)["invalidated"]
                    and item["high"] < entry
                ]
                target = max((item["high"] for item in opposing), default=None)

            if not confirms or target is None:
                continue

            risk = abs(entry - stop)
            reward = abs(target - entry)
            if risk <= 0 or reward / risk < 2.0:
                continue

            context_bias = context["bias"]
            aligned = context_bias == ("bullish" if side == "BUY" else "bearish")
            filters = self._entry_filters(data, side)
            filter_details = (
                f"entry RVOL {filters['rvol']:.2f}x, "
                f"close {filters['vwap_relation']} VWAP and "
                f"{filters['ema_relation']} 20 EMA"
            )
            return {
                "strategy": STRATEGY_NAME,
                "side": side,
                "entry": round(entry, 4),
                "stop_loss": round(stop, 4),
                "target": round(float(target), 4),
                "confidence": (
                    "HIGH"
                    if (
                        not is_estimated
                        and aligned
                        and lifecycle["retests"] == 1
                        and filters["aligned"]
                    )
                    else "MEDIUM"
                ),
                "data_quality": "ESTIMATED" if is_estimated else "VERIFIED",
                "rationale": (
                    ("ESTIMATED snapshot-derived bars; highs/lows omit intra-interval moves and wicks. "
                     if is_estimated else "")
                    +
                    f"{zone['type'].title()} zone {zone['low']:.2f}-{zone['high']:.2f}; "
                    f"{evidence}; {lifecycle['retests']} retest(s), "
                    f"{'fresh' if lifecycle['retests'] == 1 else 'retested'}; "
                    f"departure {zone['departure_atr']:.2f} ATR, "
                    f"RVOL {zone['departure_rvol']:.2f}x; "
                    f"15m context {context_bias}; {filter_details}; "
                    "target is nearest opposing zone."
                ),
            }
        return None

    @staticmethod
    def _validated_session(
        candles: pd.DataFrame,
    ) -> Optional[Tuple[pd.DataFrame, Dict[str, str]]]:
        if not isinstance(candles, pd.DataFrame):
            return None
        metadata = candles.attrs
        is_verified = metadata.get("verified_ohlcv") is True
        is_permitted_estimate = (
            metadata.get("data_source") == "synthetic_estimate"
            and metadata.get("allow_estimated_ohlcv") is True
        )
        if (
            not (is_verified or is_permitted_estimate)
            or metadata.get("timeframe") != "5m"
            or metadata.get("timezone") not in ("Asia/Kolkata", "IST")
        ):
            return None
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(candles.columns):
            return None

        data = candles.copy()
        try:
            data["timestamp"] = pd.to_datetime(data["timestamp"], errors="raise")
            data[list(required - {"timestamp"})] = data[
                list(required - {"timestamp"})
            ].apply(pd.to_numeric, errors="raise")
        except (TypeError, ValueError):
            return None
        if data[list(required)].isnull().any().any():
            return None
        if data["timestamp"].dt.tz is None:
            return None
        if str(data["timestamp"].dt.tz) != "Asia/Kolkata":
            return None
        data = data.sort_values("timestamp").reset_index(drop=True)
        if data["timestamp"].duplicated().any():
            return None
        if (
            (data["high"] < data[["open", "close", "low"]].max(axis=1)).any()
            or (data["low"] > data[["open", "close", "high"]].min(axis=1)).any()
            or (data["volume"] < 0).any()
            or (not is_permitted_estimate and (data["volume"] <= 0).any())
            or (is_permitted_estimate and data["volume"].sum() <= 0)
        ):
            return None

        session_date = data["timestamp"].iloc[-1].date()
        data = data[data["timestamp"].dt.date == session_date].reset_index(drop=True)
        if len(data) < 40:
            return None
        session_minutes = data["timestamp"].dt.hour * 60 + data["timestamp"].dt.minute
        if ((session_minutes < 9 * 60 + 15) | (session_minutes > 15 * 60 + 25)).any():
            return None
        deltas = data["timestamp"].diff().dropna()
        if not (deltas == pd.Timedelta(minutes=5)).all():
            return None

        context = SupplyDemandStrategy._fifteen_minute_context(data)
        if context is None:
            return None
        return data, context

    @staticmethod
    def _fifteen_minute_context(data: pd.DataFrame) -> Optional[Dict[str, str]]:
        """Aggregate only complete, correctly aligned groups of three 5m candles."""
        rows = []
        for _, group in data.groupby(data["timestamp"].dt.date, sort=True):
            minutes = group["timestamp"].dt.hour * 60 + group["timestamp"].dt.minute
            slots = ((minutes - 9 * 60 - 15) // 15).astype(int)
            for _, block in group.groupby(slots, sort=True):
                if len(block) != 3:
                    continue
                times = block["timestamp"].tolist()
                if any(times[index + 1] - times[index] != pd.Timedelta(minutes=5) for index in range(2)):
                    continue
                rows.append({
                    "timestamp": times[-1],
                    "high": float(block["high"].max()),
                    "low": float(block["low"].min()),
                    "close": float(block["close"].iloc[-1]),
                })
        if len(rows) < 3:
            return None
        closes = [row["close"] for row in rows[-3:]]
        bias = "bullish" if closes[-1] > closes[0] else "bearish" if closes[-1] < closes[0] else "neutral"
        return {"bias": bias}

    @staticmethod
    def _atr(data: pd.DataFrame, period: int = 14) -> List[float]:
        return TechnicalIndicators.calculate_atr(data.to_dict("records"), period=period)

    def _find_zones(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        atr_values = self._atr(data)
        volumes = data["volume"].astype(float).tolist()
        zones = []
        for base_start in range(4, len(data) - 7):
            base_atr = float(atr_values[base_start])
            if base_atr <= 0:
                continue
            prior_swings = self._confirmed_swings(data, base_start)
            if not prior_swings:
                continue
            for base_count in range(1, 6):
                base_end = base_start + base_count - 1
                if base_end + 1 >= len(data):
                    break
                base = data.iloc[base_start:base_end + 1]
                base_low = float(base["low"].min())
                base_high = float(base["high"].max())
                if base_high - base_low > base_atr:
                    continue
                for departure_end in range(base_end + 1, min(base_end + 4, len(data))):
                    departure = data.iloc[base_end + 1:departure_end + 1]
                    rvols = []
                    for index in range(base_end + 1, departure_end + 1):
                        if index < 20:
                            continue
                        baseline = sum(volumes[index - 20:index]) / 20
                        if baseline > 0:
                            rvols.append(volumes[index] / baseline)
                    if not rvols or max(rvols) <= 1.5:
                        continue
                    ranges = (departure["high"] - departure["low"]).replace(0, float("nan"))
                    body_ratios = (departure["close"] - departure["open"]).abs() / ranges
                    bullish_departure = (
                        (departure["close"] > departure["open"])
                        & (body_ratios >= 0.60)
                    ).any()
                    bearish_departure = (
                        (departure["close"] < departure["open"])
                        & (body_ratios >= 0.60)
                    ).any()
                    closes = departure["close"]
                    departure_atr = (float(closes.max()) - base_high) / base_atr
                    if (
                        bullish_departure
                        and departure_atr >= 1.5
                        and any(float(closes.max()) > swing for swing in prior_swings)
                    ):
                        zones.append({
                            "type": "demand", "low": base_low, "high": base_high,
                            "base_start": base_start, "base_end": base_end,
                            "created": departure_end, "departure_atr": departure_atr,
                            "departure_rvol": max(rvols),
                        })
                    supply_departure_atr = (base_low - float(closes.min())) / base_atr
                    if (
                        bearish_departure
                        and supply_departure_atr >= 1.5
                        and any(float(closes.min()) < swing for swing in prior_swings)
                    ):
                        zones.append({
                            "type": "supply", "low": base_low, "high": base_high,
                            "base_start": base_start, "base_end": base_end,
                            "created": departure_end, "departure_atr": supply_departure_atr,
                            "departure_rvol": max(rvols),
                        })
                    if zones and zones[-1]["base_start"] == base_start and zones[-1]["base_end"] == base_end:
                        break
        unique_zones = {}
        for zone in zones:
            key = (
                zone["type"],
                round(zone["low"], 4),
                round(zone["high"], 4),
                zone["created"],
            )
            unique_zones.setdefault(key, zone)
        return list(unique_zones.values())

    @staticmethod
    def _confirmed_swings(data: pd.DataFrame, before_index: int) -> List[float]:
        swings = []
        for index in range(2, before_index - 2):
            highs = data["high"].iloc[index - 2:index + 3].astype(float).tolist()
            if highs[2] == max(highs) and highs.count(highs[2]) == 1:
                swings.append(highs[2])
        return swings

    @staticmethod
    def _zone_lifecycle(data: pd.DataFrame, zone: Dict[str, Any]) -> Dict[str, Any]:
        retests = 0
        current_retest = False
        invalidated = False
        was_touching = False
        for index in range(zone["created"] + 1, len(data)):
            candle = data.iloc[index]
            if zone["type"] == "demand":
                if float(candle["close"]) < zone["low"]:
                    invalidated = True
                    break
                touched = float(candle["low"]) <= zone["high"] and float(candle["high"]) >= zone["low"]
            else:
                if float(candle["close"]) > zone["high"]:
                    invalidated = True
                    break
                touched = float(candle["high"]) >= zone["low"] and float(candle["low"]) <= zone["high"]
            if touched:
                if not was_touching:
                    retests += 1
                current_retest = index >= len(data) - 2
            else:
                current_retest = False
            was_touching = touched
        return {
            "retests": retests,
            "current_retest": current_retest,
            "invalidated": invalidated,
        }

    @staticmethod
    def _bullish_confirmation(current: pd.Series, previous: pd.Series, zone: Dict[str, Any]) -> Tuple[bool, str]:
        body = abs(float(current["close"]) - float(current["open"]))
        lower_wick = min(float(current["open"]), float(current["close"])) - float(current["low"])
        rejection = (
            float(current["close"]) > float(current["open"])
            and float(current["close"]) > zone["high"]
            and lower_wick + 1e-9 >= body
        )
        engulfing = (
            float(previous["close"]) < float(previous["open"])
            and float(current["close"]) > float(current["open"])
            and float(current["open"]) <= float(previous["close"])
            and float(current["close"]) >= float(previous["open"])
        )
        if rejection:
            return True, "bullish rejection closed above zone"
        if engulfing and float(current["close"]) > zone["low"]:
            return True, "bullish engulfing at zone"
        return False, ""

    @staticmethod
    def _bearish_confirmation(current: pd.Series, previous: pd.Series, zone: Dict[str, Any]) -> Tuple[bool, str]:
        body = abs(float(current["close"]) - float(current["open"]))
        upper_wick = float(current["high"]) - max(float(current["open"]), float(current["close"]))
        rejection = (
            float(current["close"]) < float(current["open"])
            and float(current["close"]) < zone["low"]
            and upper_wick + 1e-9 >= body
        )
        engulfing = (
            float(previous["close"]) > float(previous["open"])
            and float(current["close"]) < float(current["open"])
            and float(current["open"]) >= float(previous["close"])
            and float(current["close"]) <= float(previous["open"])
        )
        if rejection:
            return True, "bearish rejection closed below zone"
        if engulfing and float(current["close"]) < zone["high"]:
            return True, "bearish engulfing at zone"
        return False, ""

    @staticmethod
    def _tick_size(candles: pd.DataFrame) -> float:
        tick_size = candles.attrs.get("tick_size", 0.05)
        try:
            value = float(tick_size)
        except (TypeError, ValueError):
            return 0.05
        return value if value > 0 else 0.05

    @staticmethod
    def _entry_filters(data: pd.DataFrame, side: str) -> Dict[str, Any]:
        volumes = data["volume"].astype(float)
        baseline = float(volumes.iloc[-21:-1].mean())
        rvol = float(volumes.iloc[-1] / baseline) if baseline > 0 else 0.0
        typical_price = (data["high"] + data["low"] + data["close"]) / 3.0
        vwap = float((typical_price * volumes).sum() / volumes.sum())
        ema20 = float(data["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        close = float(data["close"].iloc[-1])
        if side == "BUY":
            vwap_aligned = close > vwap
            ema_aligned = close > ema20
            vwap_relation = "above" if vwap_aligned else "below"
            ema_relation = "above" if ema_aligned else "below"
        else:
            vwap_aligned = close < vwap
            ema_aligned = close < ema20
            vwap_relation = "below" if vwap_aligned else "above"
            ema_relation = "below" if ema_aligned else "above"
        return {
            "rvol": rvol,
            "vwap_relation": vwap_relation,
            "ema_relation": ema_relation,
            "aligned": rvol > 1.0 and (vwap_aligned or ema_aligned),
        }
