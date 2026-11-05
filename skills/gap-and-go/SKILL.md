---
name: gap-and-go
description: "Intraday Gap and Go strategy for Indian markets (NSE/BSE). Identifies overnight pre-market gaps (> 1.5% to 3.0%), verifies morning price acceptance (09:15 - 09:30 IST), and enters high-momentum trend continuation moves."
strategy_type: "gap_and_go"
market: "Indian Equities (NSE/BSE), Heavyweight Stocks"
ideal_time_window: "09:00 AM (Pre-market scan) & 09:20 AM - 10:15 AM IST (Execution)"
chart_timeframes: ["5m", "15m"]
risk_level: "Moderate to High (Requires tight gap-fill invalidation rules)"
---

# Gap and Go Strategy (Indian Intraday Markets)

Based on the Flattrade Indian Intraday Trading framework: **"When a stock opens significantly higher or lower than yesterday's close due to major overnight news or earnings, the Gap and Go strategy bets that the stock will continue aggressively in the direction of the gap rather than filling it."**

---

## 1. Indian Pre-Market Discovery & Gap Anatomy

In Indian markets:
- **09:00 AM – 09:08 AM IST**: The NSE/BSE pre-market call auction establishes the opening price equilibrium based on overnight news, GIFT Nifty direction, and earnings filings.
- **09:08 AM – 09:15 AM IST**: Order buffer and transition to the normal market.
- **Gap Significance**:
  - Gaps $> 1.5\%$ in large-caps signify substantial institutional repositioning.
  - The crucial test occurs in the **first 5 to 15 minutes (09:15 – 09:30 IST)**: if institutional buyers aggressively absorb early profit-takers, the stock will NOT fill the gap and will instead expand ("Go").

---

## 2. Pre-Market Screening Criteria (09:08 AM IST)

At 09:08 AM IST, scan the NSE Pre-Open market data:
1. **Gap Size**:
   - Minimum: $\ge 1.5\%$ above or below yesterday's closing price.
   - Maximum: $\le 4.5\%$ (gaps $> 5\%$ often experience immediate exhaustion or circuit limit freeze).
2. **Fundamental / News Catalyst**:
   - Quarterly earnings beat/miss, major corporate contract, regulatory clearance, credit rating revision, or strong global sector correlation.
3. **Liquidity**:
   - Pre-market traded volume $\ge 50,000$ shares for equities priced $> ₹500$.

---

## 3. Morning Acceptance Criteria (09:15 – 09:30 AM IST)

Do not blindly buy at 09:15:01 AM! Wait for the first 5-minute candle to print:
- **Gap and Go Long Confirmation**:
  - The first 5-minute candle closes green (Close > Open).
  - The low of the first 5-minute candle stays **strictly above** yesterday's close (no gap fill attempt).
  - Price holds above the opening tick price.
  - Volume on the first 5-minute candle is among the highest 5m volume bars of the month.
- **Gap and Go Short Confirmation**:
  - The first 5-minute candle closes red (Close < Open).
  - The high of the candle stays below yesterday's close.
  - Selling volume dominates the tape.

---

## 4. Entry Rules

### Gap and Go Long
1. **Trigger**: At 09:20 AM or 09:30 AM IST, price breaks above the high of the opening 5-minute (or 15-minute) candle.
2. **Confirmation**:
   - Price > Intraday VWAP.
   - 5-minute RSI is crossing or sustained above 65.
3. **Execution**: Place an MIS BUY order upon breakout of the opening candle high.

### Gap and Go Short
1. **Trigger**: Price breaks below the low of the opening 5-minute or 15-minute candle following a gap down.
2. **Confirmation**: Price < Intraday VWAP; RSI < 35.
3. **Execution**: Place an MIS SELL order upon breakdown.

---

## 5. Stop-Loss & Target Rules

1. **Stop-Loss (The Gap-Fill Invalidation)**:
   - For Longs: Place Stop-Loss at the **low of the first 5-minute candle** (or max $1.0\%$ below entry). If price breaks below the morning candle low, the gap is likely filling; exit immediately!
   - For Shorts: Place Stop-Loss at the **high of the first 5-minute candle** (or max $1.0\%$ above entry).
2. **Profit Targets**:
   - **Target 1**: $1.0 \times$ the gap size added to the opening price.
   - **Target 2**: Next major Fibonacci expansion or Daily Pivot level (R2/S2).
   - Aim for a minimum Risk-to-Reward ratio of **1:2**.
3. **Time-Based Exit**:
   - If momentum stalls by 11:30 AM, book at least $60\%$ profits.
   - Mandatory MIS square-off before 15:20 IST.

---

## 6. Claude Agent Execution Protocol

```mermaid
flowchart TD
    A[09:08 IST: Scan NSE Pre-Open Session] --> B[Filter Symbols with Gap >= 1.5% and News Catalyst]
    B --> C[09:15 IST: Market Opens - Observe First 5-min Candle]
    C --> D{Did Candle Close in Gap Direction with High Volume?}
    D -->|No: Large Wick / Reversal| E[Discard - Potential Gap Fade / Trap]
    D -->|Yes: Strong Body & Vol| F{Price breaks 5m High (Long) or Low (Short)?}
    F -->|No Breakout| G[Wait for 15m Candle Formation]
    F -->|Breaks Opening Range High| H[Calculate Position Size: SL @ Opening Candle Low]
    H --> I[Place MIS BUY Order]
    I --> J{Track Position}
    J -->|Price drops below 5m Candle Low| K[Immediate Invalidation Exit: Stop Gap-Fill]
    J -->|Target 1 Reached| L[Book 50%, Trail SL to Opening Price]
    J -->|Time == 15:15 IST| M[Square Off All Open Contracts]
```

### Actionable Commands for Claude Agent:
```python
# Pre-market scan
gappers = tools.scan_premarket_gaps(min_gap_pct=1.5, max_gap_pct=4.5)

for stock in gappers:
    state = tools.get_market_state(symbol=stock["symbol"])
    candle_5m = tools.get_candle(symbol=stock["symbol"], timeframe="5m", index=0)
    
    # Verify Gap and Go Long criteria
    if stock["gap_pct"] > 0 and candle_5m["close"] > candle_5m["open"]:
        if state["ltp"] > candle_5m["high"]:
            entry = state["ltp"]
            stop_loss = candle_5m["low"]
            
            # Risk check: ensure SL is within 1%
            if (entry - stop_loss) / entry <= 0.012:
                target = round(entry + (entry - stop_loss) * 2, 2)
                pos_size = tools.calculate_position_size(
                    capital=account.capital,
                    risk_pct=0.015,
                    entry=entry,
                    stop_loss=stop_loss
                )
                
                tools.place_order(
                    symbol=stock["symbol"],
                    side="BUY",
                    product="MIS",
                    quantity=pos_size,
                    price=entry,
                    stop_loss=stop_loss,
                    target=target,
                    strategy="gap_and_go"
                )
                break
```

---

## 7. Edge Cases & Traps

- **The Gap-Fade Trap**: The biggest hazard in gap trading is institutional distribution into retail morning hype. If the opening candle has a huge upper wick ($> 40\%$ of candle range), retail is being sold into. **Do not buy**.
- **Earnings Blackout / Pre-result Suspense**: Never hold gap trades across corporate result announcement conferences happening mid-session.
