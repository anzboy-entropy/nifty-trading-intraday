---
name: pivot-vwap-ema
description: "Rule-based intraday strategy for Indian equities and indices using Classic Daily Pivot Points, 5-minute VWAP, and 20 EMA. Use to evaluate bullish or bearish confluence, confirmation candles, volume, entries, targets, and risk."
strategy_type: "trend_confluence"
market: "Indian Equities and Indices (NSE/BSE)"
chart_timeframes: ["5m"]
pivot_variant: "Classic"
---

# Classic Pivot Points + VWAP + 20 EMA

## Purpose

Look for 5-minute directional setups only when price action agrees with the prior
session's Classic Daily Pivot levels, intraday VWAP, and the 20-period EMA. This
skill describes candidate setups; it does not guarantee outcomes or authorize
placing orders without the user's approval and the system's risk checks.

## Required Data and Indicators

- Use completed 5-minute OHLCV candles from the current regular session.
- Calculate VWAP from current-session trades/candles; reset it at the session open.
- Calculate the 20 EMA on the 5-minute close series.
- Calculate Classic Daily Pivot levels from the previous completed session's
  high (H), low (L), and close (C):

  - `P = (H + L + C) / 3`
  - `R1 = 2P - L`; `S1 = 2P - H`
  - `R2 = P + (H - L)`; `S2 = P - (H - L)`
  - `R3 = H + 2(P - L)`; `S3 = L - 2(H - P)`

- Confirm the OHLC source, session date, timezone, and adjustment basis. Do not
  silently substitute incomplete, stale, synthetic, or current-session OHLC for
  the prior session's completed values. If required inputs or indicator history
  are unavailable, return **no setup** and state what is missing.

## Long Setup

Evaluate only after a 5-minute candle has closed. A candidate BUY requires all
of the following on that confirmation candle:

1. Its close is strictly above the central pivot `P`.
2. Its close is strictly above the 20 EMA.
3. Its close is strictly above VWAP.
4. It is bullish (`close > open`) and closes above all three levels.
5. Volume supports the move: confirmation-candle volume must exceed the mean
   volume of the preceding 20 completed 5-minute candles. Reject low-volume
   drift; if the baseline is unavailable, do not claim volume confirmation.
6. The candle is not an unusually extended spike. The scanner rejects a candle
   body larger than 1.5 times the 14-period 5-minute ATR; avoid chasing a close
   far from the confluence levels.

**Entry:** Candidate entry is the confirmation candle close. State clearly that
the actual fill can differ, especially if price gaps or moves before execution.

**Stop:** The scanner places the hard stop just below the confirmation candle
low. Alternatively, a manual plan may use the nearest relevant confluence
support (VWAP or `P`) with an instrument-appropriate buffer. Choose one
structural invalidation level before sizing; do not widen the stop after entry.
The stop must be below entry.

**Target:** Evaluate `R1`, then `R2`, then `R3`. Use the nearest resistance level
that offers at least 2:1 reward-to-risk from the proposed entry and stop. If no
resistance target offers at least 2:1, skip the trade rather than inventing a
target beyond `R3`.

## Short Setup

Evaluate only after a 5-minute candle has closed. A candidate SELL/short requires
all of the following on that confirmation candle:

1. Its close is strictly below the central pivot `P`.
2. Its close is strictly below the 20 EMA.
3. Its close is strictly below VWAP.
4. It is bearish (`close < open`) and closes below all three levels.
5. Volume supports the move, assessed against a recent completed 5-minute volume
   baseline as described above.
6. The candle is not an unusually extended downside spike; avoid chasing a close
   far below the confluence levels.

**Entry:** Candidate entry is the confirmation candle close; actual execution
may differ.

**Stop:** The scanner places the hard stop just above the confirmation candle
high. Alternatively, a manual plan may use the nearest relevant confluence
resistance (VWAP or `P`) with an instrument-appropriate buffer. Select and fix
the structural invalidation level before sizing. The stop must be above entry.

**Target:** Evaluate `S1`, then `S2`, then `S3`. Use the nearest support level
that offers at least 2:1 reward-to-risk. If no support target offers the minimum
2:1 ratio, skip the trade.

## No-Trade Filters

- Price is repeatedly crossing VWAP, `P`, and the 20 EMA, with no clear
  directional acceptance.
- The confirmation candle is incomplete, data is stale, or required prior-day
  OHLC/volume history is missing.
- Volume does not support the breakout/acceptance.
- The nearest viable pivot target cannot provide at least 2:1 reward-to-risk.
- The proposed quantity violates account risk, margin, liquidity, or broker
  constraints.
- New entries are not permitted by the applicable session rules, including the
  intraday square-off cutoff.
- Conditions are unusually erratic (including expiry/event-driven sessions);
  reduce exposure or stand aside when price action is not orderly.

## Risk and Execution Rules

1. Treat the setup as a signal for review, not a prediction or guaranteed trade.
2. Require an exchange/broker-supported hard stop before considering a position.
3. Size from the actual planned stop distance:

   `quantity = floor((capital * risk_fraction) / abs(entry - stop))`

   Apply the account's stricter configured risk cap, leverage/margin limit,
   liquidity limits, and daily loss controls. Never exceed a 2% capital risk
   ceiling per trade; a lower account limit takes precedence.
4. Account for slippage, spread, statutory charges, and instrument lot sizes.
   For index derivatives, round quantity to valid lots and calculate risk using
   the contract multiplier.
5. Do not average down, move a stop farther away, or increase risk after entry.
6. Follow the broker's product rules and close intraday positions before its
   mandatory square-off deadline.
7. Record the timestamp, instrument, side, prior-session OHLC and pivot levels,
   VWAP, 20 EMA, confirmation candle OHLCV, entry, stop, target, quantity,
   rationale, and outcome in the trade journal.

## Candidate Output

For each evaluated instrument, report either **NO SETUP** with the failed
conditions, or provide:

- Snapshot/candle timestamp and data freshness
- Instrument, side, and confirmation candle close
- Prior-session H/L/C and `P`, `R1`-`R3`, `S1`-`S3`
- Confirmation close, VWAP, 20 EMA, candle direction/body, and volume check
- Proposed entry, selected stop and invalidation rationale, pivot target, and
  reward-to-risk
- Risk-based quantity or why sizing could not be calculated
- Any data-quality, liquidity, event, or session caveats

## Scanner Data Availability

The current dashboard NSE collector stores periodic market snapshots, not
completed 5-minute OHLCV candles. The live scanner therefore suppresses this
strategy for snapshot-derived or synthesized series. It only evaluates candles
explicitly marked as verified 5-minute OHLCV and requires archived prior-session
high, low, and close data. Do not remove this data-quality gate by treating
snapshot estimates as completed candles.
