---
name: supply-demand
description: "Analyze intraday supply and demand zones from verified 5-minute OHLCV, with 15-minute market-structure context, zone freshness, retest confirmation, VWAP/EMA/volume filters, and risk-defined trade plans. Use for supply-demand, institutional-zone, absorption, rejection, breakout, and retest analysis."
---

# Intraday Supply and Demand Zones

## Purpose and Limits

Identify candidate demand zones (areas associated with a strong bullish
departure) and supply zones (areas associated with a strong bearish departure)
using completed 5-minute OHLCV candles. Use 15-minute structure for directional
context and 5-minute candles for zone retests and entries.

OHLCV patterns are observable price-and-volume behavior, not proof of
institutional orders, absorption, or participant identity. Describe zones as
candidate areas of supply or demand; do not claim to know who placed the
orders. This is a decision-support method, not a prediction or a guarantee.
Do not place orders without explicit user authorization and applicable risk
checks.

## Required Data

- Verified, time-ordered 5-minute OHLCV candles for the current session and
  enough preceding candles to calculate ATR, relative volume, and swing
  structure.
- Reliable timestamps with a known timezone, instrument, exchange session, and
  regular-session boundaries.
- Either verified 15-minute OHLCV or 15-minute candles aggregated from three
  consecutive, complete, correctly aligned 5-minute candles.
- No synthetic, interpolated, snapshot-derived, incomplete, duplicate, or stale
  candles for zone detection or entry confirmation.
- Positive volume values from a consistent source. If volume is unavailable or
  unreliable, do not claim volume confirmation.

If these requirements are not met, return **NO VALID ZONE / NO SETUP** and state
which inputs are missing. Never fill gaps by repeating prices or inventing
candles.

## Candle Metrics and Initial Parameters

Use the following initial settings as hypotheses to test, not universal
constants:

- ATR: 14-period Wilder ATR on completed 5-minute candles.
- Relative volume (RVOL): candidate candle volume divided by the mean volume of
  the preceding 20 completed 5-minute candles, excluding the candidate candle.
- Base: 1 to 5 consecutive candles whose combined high-low range is no more than
  1.0 times the 5-minute ATR measured at the start of the base. The base should
  show limited directional progress; do not call a wide, one-way move a base.
- Departure: the move after the base must close at least 1.5 times the
  pre-departure ATR beyond the relevant base edge within the next 1 to 3
  completed candles. At least one departure candle must have body/range of
  0.60 or greater, where body/range is `abs(close - open) / (high - low)`.
  Treat a zero-range candle as invalid for this ratio.
- Participation: at least one departure candle must have RVOL greater than 1.5.
- Structure: the departure must close beyond a confirmed prior swing high for
  demand or swing low for supply. Define swing points consistently (for example,
  a pivot with two completed lower highs on each side for a swing high, and two
  higher lows on each side for a swing low). A swing is not confirmed until the
  required candles to its right have closed.

Record the exact settings used with every analysis. Do not tune thresholds on
the evaluation period or imply they are optimized without out-of-sample
testing.

## Zone Construction and Lifecycle

1. Scan completed candles chronologically. Identify a qualifying base followed
   by a qualifying departure. Do not use future candles to label a zone as
   available at an earlier time.
2. Record the base start/end time, candle count, base high, base low, departure
   size in ATR units, maximum departure RVOL, and the broken swing level.
3. Use the full base range for the zone:
   - Demand: distal boundary is base low; proximal boundary is base high.
   - Supply: proximal boundary is base low; distal boundary is base high.
4. A zone is created only after its departure and structure break have been
   confirmed on candle close. A revisit before confirmation cannot count as a
   post-creation retest.
5. A zone is **fresh** if price has not returned to its proximal boundary since
   confirmation. Count each later entry into the zone as a retest. Report the
   retest count; repeated tests generally reduce freshness and should not
   increase a zone's score.
6. Invalidate demand after a completed candle closes below its distal boundary;
   invalidate supply after a completed candle closes above its distal boundary.
   A wick through a boundary is a warning, not by itself a close-based
   invalidation. State the boundary and rule explicitly.
7. Report zone age in elapsed regular-session time and number of completed
   5-minute candles since creation. Do not carry a zone into a new session
   without explicitly identifying it as a prior-session zone and revalidating
   it against the current session.
8. A gap across a zone is not a confirmed defended retest. Mark it as skipped or
   gapped through and wait for fresh evidence.

## Relative Zone Assessment

Assess evidence transparently rather than presenting a subjective “institutional
strength” as fact. Report:

- Departure distance in ATR units.
- Departure candle body/range and close location within its range.
- Maximum departure RVOL and the baseline window.
- Whether a confirmed swing level was broken and by how much.
- Base candle count and width in ATR units.
- Age, retest count, and whether the zone is fresh.
- Whether price has since closed through the zone or gapped across it.

Stronger displacement, supported volume, and a confirmed structure break are
positive evidence. Greater age, multiple retests, weak departure, or nearby
opposing zones are cautionary evidence. Do not combine these into an unexplained
score or treat any one metric as proof of future support or resistance.

## Market Context and Filters

Before considering a trade, report the 15-minute structure: recent confirmed
swing sequence, relevant break of structure, and whether price is making higher
highs/higher lows, lower highs/lower lows, or is range-bound. Prefer demand
setups when higher-timeframe context is constructive and supply setups when it
is weak; countertrend trades require especially clear confirmation and must
still satisfy risk rules.

Use the following as context, not independent entry signals:

- Session VWAP and 20-period EMA on 5-minute closes.
- RVOL based only on prior completed candles.
- RSI(14), if available, as a momentum check; do not treat overbought or
  oversold readings alone as reversal signals.
- Previous session high/low and the regular-session opening range.
- Distance to the nearest opposing zone and available reward-to-risk.

Avoid or explicitly flag low-liquidity periods, unusually wide spreads, major
scheduled events, erratic price action, and sessions with insufficient candle
history. Do not call a zone a breakout until a completed candle closes outside
it. A breakout followed by a retest is a distinct setup from a reversal at a
zone.

## Demand-Zone Long Setup

Consider a long only when all required data is valid and:

1. A valid demand zone has been confirmed, is not invalidated, and price returns
   to it after zone creation.
2. Price reaches or overlaps the zone; entry is not triggered merely because
   price touches it.
3. A completed 5-minute confirmation candle shows buyer response, such as a
   bullish rejection (lower wick with a close back above the proximal boundary),
   a bullish engulfing pattern, or a decisive bullish close out of the zone.
   Name the exact pattern/condition observed; do not use vague “absorption”
   claims.
4. Prefer confirmation with RVOL above 1.0 and close above the 5-minute VWAP
   and/or 20 EMA. If those filters disagree, report the disagreement and lower
   confidence; do not silently waive a configured filter.
5. There is a plausible target at the next opposing supply zone or other
   predeclared resistance, and the target offers at least 2:1 reward-to-risk
   after allowing for an appropriate buffer and estimated costs. Otherwise,
   report **NO TRADE**.

**Entry trigger:** A buy-stop candidate one valid tick above the confirmation
candle high, active only after that candle closes. The actual fill may differ.

**Stop:** Below the demand-zone distal boundary with an instrument-appropriate
buffer. If the required stop makes the trade's risk too large or violates the
minimum reward-to-risk, skip the trade; do not move the stop closer merely to
force a trade.

**Target:** The next valid opposing supply zone or predeclared resistance. Use
the nearer realistic target when multiple targets exist. Do not assume price
will reach a zone.

## Supply-Zone Short Setup

Apply the exact inverse only when short selling is permitted for the instrument:

1. Price returns to an uninvalidated supply zone after it is confirmed.
2. A completed 5-minute candle shows seller response: for example, an upper-wick
   rejection that closes back below the proximal boundary, a bearish engulfing
   pattern, or a decisive bearish close out of the zone.
3. Prefer RVOL above 1.0 and a close below 5-minute VWAP and/or the 20 EMA.
   Report conflicts rather than hiding them.
4. The next opposing demand zone or predeclared support offers at least 2:1
   reward-to-risk after buffers and estimated costs.

**Entry trigger:** A sell-stop candidate one valid tick below the confirmation
candle low, active only after that candle closes.

**Stop:** Above the supply-zone distal boundary with an instrument-appropriate
buffer. Skip if this stop cannot fit the risk limit or the target cannot satisfy
minimum reward-to-risk.

**Target:** The next valid opposing demand zone or predeclared support. Confirm
that short selling and the selected product are allowed by the user's broker and
applicable rules.

## Breakout and Retest

Treat a breakout as valid only after a completed 5-minute close outside the
zone, with meaningful displacement and participation. A wick outside the zone
alone is not a breakout.

For a bullish break above supply or a bearish break below demand, wait for a
subsequent retest of the broken boundary and a completed candle confirming
acceptance on the breakout side. Do not enter on the initial break if the move
is already extended or if the next opposing zone prevents at least 2:1
reward-to-risk. A close back into and through the zone is a failed-breakout
warning and invalidates that breakout thesis.

## Risk and Execution

1. Treat every output as a candidate plan, not an instruction to trade.
2. Calculate quantity from the entry-to-stop distance:

   `quantity = floor(allowed_risk_amount / (abs(entry - stop) * point_value))`

   For cash equities, point value is normally one currency unit per share; for
   derivatives, use the actual contract multiplier and valid lot size.
3. `allowed_risk_amount` must respect the user's configured risk cap, account
   rules, and daily loss limits. Never exceed a 2% capital risk ceiling per
   trade; a stricter configured limit takes precedence.
4. Include spread, slippage, fees, liquidity, margin, lot-size constraints, and
   gap risk. Do not average down, widen a stop, or increase risk after entry.
5. Follow the broker's product rules and mandatory intraday square-off
   deadline. Require explicit user authorization before any order is placed.
6. If market data becomes stale, stops cannot be placed, or the zone is
   invalidated before entry, cancel the candidate setup.

## Backtesting and Validation

- Backtest on verified OHLCV with the same session, timezone, instrument, and
  execution assumptions intended for live use.
- Use only information available at each candle close. Include right-side
  confirmation delay for swings, signal-candle delay for entry, tick size,
  transaction costs, slippage, rejected/partial fills, and gaps.
- Prevent look-ahead and survivorship bias. Split development, validation, and
  out-of-sample periods chronologically; avoid selecting thresholds on the test
  set.
- Compare results against simple baselines and report sample size, expectancy,
  win rate, average win/loss, maximum drawdown, and performance by instrument
  and market regime. A profitable historical sample is not a guarantee of
  future performance.
- Do not describe the initial thresholds as “effective” or “optimized” until
  they pass robust out-of-sample and realistic execution testing.

## Required Output

For every instrument, return either **NO VALID DATA**, **NO VALID ZONE**, or a
candidate setup. Include:

- Data source, instrument, timezone, candle interval, latest completed candle
  timestamp, freshness, and any missing-data caveat.
- 15-minute structure and current-session context.
- Zone type and boundaries, creation time, base candle count/range, departure
  distance in ATR, RVOL, broken swing, age, retest count, freshness, and
  invalidation status.
- Retest/confirmation candle OHLCV and the precise confirmation evidence.
- VWAP, 20 EMA, optional RSI, and relevant previous-session/opening-range levels.
- Candidate entry trigger, stop and invalidation level, target, estimated
  reward-to-risk, and risk-based quantity or why sizing is unavailable.
- Reasons for rejecting a setup, including opposing-zone distance, weak
  participation, stale/incomplete data, conflicting context, or unacceptable
  risk.

## Integration Boundary

This skill defines analysis guidance only. It does not imply the live scanner
uses true 5-minute OHLCV, calculate historical zones from snapshot estimates,
or enable automatic trading. Any scanner integration must independently verify
the candle source and preserve explicit data-quality and risk gates.
