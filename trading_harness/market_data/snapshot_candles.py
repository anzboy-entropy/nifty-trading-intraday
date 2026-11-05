"""Exploratory OHLCV estimates built from periodic NSE snapshots."""

from typing import Dict, List

import pandas as pd


CANDLE_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
IST_TIMEZONE = "Asia/Kolkata"
MARKET_OPEN_MINUTES = 9 * 60 + 15
MARKET_CLOSE_MINUTES = 15 * 60 + 30
BAR_MINUTES = 5
SNAPSHOT_TOLERANCE_SECONDS = 60


def synthesize_5m_candles(snapshots: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Estimate 5-minute bars from consecutive, clock-aligned snapshots.

    The estimated high and low are limited to the two observed endpoint prices;
    intrainterval price movement and true wicks cannot be recovered.
    """
    if snapshots.empty or not {
        "snapshot_ist", "symbol", "last_price", "volume"
    }.issubset(snapshots.columns):
        return _empty_candles()

    selected = snapshots.loc[snapshots["symbol"] == symbol].copy()
    if selected.empty:
        return _empty_candles()

    timestamps = pd.to_datetime(selected["snapshot_ist"], errors="coerce")
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(IST_TIMEZONE)
    else:
        timestamps = timestamps.dt.tz_convert(IST_TIMEZONE)
    selected["timestamp"] = timestamps
    selected["last_price"] = pd.to_numeric(selected["last_price"], errors="coerce")
    selected["volume"] = pd.to_numeric(selected["volume"], errors="coerce")
    selected = selected.dropna(subset=["timestamp", "last_price", "volume"])
    selected = selected[
        (selected["last_price"] > 0) & (selected["volume"] >= 0)
    ].sort_values("timestamp")
    selected = selected.drop_duplicates(subset=["timestamp"], keep="last")
    if selected.empty:
        return _empty_candles()

    session_open = selected["timestamp"].dt.normalize() + pd.Timedelta(
        minutes=MARKET_OPEN_MINUTES
    )
    elapsed_seconds = (selected["timestamp"] - session_open).dt.total_seconds()
    slots = (elapsed_seconds / (BAR_MINUTES * 60)).round()
    selected["_slot"] = slots.astype(int)
    selected["_mark"] = session_open + pd.to_timedelta(
        selected["_slot"] * BAR_MINUTES, unit="minutes"
    )
    selected["_mark_error"] = (
        selected["timestamp"] - selected["_mark"]
    ).abs().dt.total_seconds()
    selected = selected[
        (selected["_slot"] >= 0)
        & (selected["_mark"] <= selected["timestamp"].dt.normalize()
           + pd.Timedelta(minutes=MARKET_CLOSE_MINUTES))
        & (selected["_mark_error"] <= SNAPSHOT_TOLERANCE_SECONDS)
    ].drop_duplicates(subset=["_mark"], keep="last")

    candles: List[Dict[str, object]] = []
    for _, session in selected.groupby(selected["timestamp"].dt.date, sort=True):
        session = session.sort_values("_mark")
        previous = None
        for current in session.to_dict("records"):
            if previous is not None and current["_slot"] == previous["_slot"] + 1:
                volume_delta = current["volume"] - previous["volume"]
                if volume_delta >= 0:
                    open_price = float(previous["last_price"])
                    close_price = float(current["last_price"])
                    candles.append({
                        "timestamp": previous["_mark"],
                        "open": open_price,
                        "high": max(open_price, close_price),
                        "low": min(open_price, close_price),
                        "close": close_price,
                        "volume": float(volume_delta),
                    })
            previous = current

    result = pd.DataFrame(candles, columns=CANDLE_COLUMNS)
    result.attrs.update({
        "data_source": "synthetic_estimate",
        "timeframe": "5m",
        "timezone": IST_TIMEZONE,
        "verified_ohlcv": False,
    })
    return result


def _empty_candles() -> pd.DataFrame:
    result = pd.DataFrame(columns=CANDLE_COLUMNS)
    result.attrs.update({
        "data_source": "synthetic_estimate",
        "timeframe": "5m",
        "timezone": IST_TIMEZONE,
        "verified_ohlcv": False,
    })
    return result
