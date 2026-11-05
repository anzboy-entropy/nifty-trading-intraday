---
name: indian-market-trading-master
description: "Master Orchestration Skill for Agentic Intraday Trading in Indian Markets (NSE/BSE). Coordinates session timing, risk guardrails (1-2% max risk, MIS square-off at 15:20 IST), strategy selection matrix across all 7 Flattrade intraday setups, and trade journaling."
strategy_type: "orchestrator"
market: "NSE Equities, NIFTY & BANKNIFTY Derivatives"
---

# Indian Intraday Market Orchestration & Risk Master Guide

This master skill orchestrates the agentic execution of all 7 intraday strategies analyzed from Flattrade:
1. **Momentum Trading** (09:15 - 10:15 IST)
2. **Breakout Trading** (10:30 - 13:30 IST)
3. **Reversal Trading / Mean Reversion** (Extreme moves, fading to VWAP)
4. **VWAP Trading** (Pullback bounces, 10:15 - 14:30 IST)
5. **Scalping** (1-minute micro tick captures on SBIN, Nifty options)
6. **Gap and Go** (Pre-open scan, 09:15 - 09:45 IST)
7. **Opening Range Breakout / ORB** (09:30 - 11:00 IST)

---

## 1. The Indian Market Intraday Clock

The agent MUST govern its actions according to Indian Standard Time (IST):

| Time Window (IST) | Market Phase | Permitted Strategies | Agent Behavior |
| :--- | :--- | :--- | :--- |
| **09:00 - 09:08** | Pre-Open Auction | None (Observation) | Scan gap percentage, news catalysts, and pre-open book depth. |
| **09:08 - 09:15** | Transition Buffer | None | Calculate Opening Gap watchlist, define key levels, verify broker connection. |
| **09:15 - 10:15** | Opening Volatility Surge | **Momentum, Gap & Go, ORB (setup)** | Highest volatility. Strict hard stop-losses. Scan gainers/losers. |
| **09:30 - 11:00** | Primary Breakout Window | **ORB, Momentum continuation** | 15m candle closes; execute ORB if range size $\le 0.7\times$ ATR. |
| **10:15 - 13:30** | Trend & Midday Range | **VWAP Bounces, Range Breakouts** | Trend stabilizes. VWAP pullbacks provide prime risk-reward. |
| **11:30 - 13:30** | Lunch Hour Consolidation | **Scalping (careful), Range Breakout (formation)** | Low volume chop. Do NOT initiate fresh momentum trades. |
| **13:30 - 14:30** | Afternoon Trend Resumption | **VWAP Continuation, Breakouts, Reversals** | European market open cues (13:30 IST); volume picks up. |
| **14:30 - 15:15** | Final Square-Off Wave | **Momentum (quick trail), Scalping** | High volatility as intraday positions cover. Trail SL aggressively. |
| **15:15 - 15:20** | Mandatory Cut-Off | **NO NEW TRADES** | Square off all open MIS positions. Cancel outstanding limit orders. |
| **15:20 - 15:30** | Broker Auto Square-Off | **Account Locked** | Auto square-off charges apply if still open. Log daily review. |
| **15:30 - 16:00** | Post-Market EOD Journal | None | Generate trade journal, calculate net PnL after statutory costs. |

---

## 2. Non-Negotiable Risk Management Guardrails

From Flattrade's Core Rules:

1. **Rule 1: Always Use a Hard Stop-Loss**:
   - Every single order placed must include a stop-loss order registered in the exchange order book immediately upon fill. No naked trades.
2. **Rule 2: Never Risk More Than 1% to 2% Per Trade**:
   $$\text{Quantity} = \left\lfloor \frac{\text{Account Capital} \times \text{Risk \%}}{|\text{Entry Price} - \text{Stop-Loss Price}|} \right\rfloor$$
   If Capital is ₹1,00,000 and Risk is 1.5% (₹1,500), and entry is ₹500 with SL ₹495 (Risk = ₹5):
   $$\text{Quantity} = \frac{1500}{5} = 300 \text{ shares}$$
3. **Rule 3: Daily Kill-Switch (Maximum Drawdown)**:
   - If cumulative daily realized + unrealized loss reaches **$3.0\%$ of capital**, terminate all active trades immediately and disallow further trade placement for the remainder of the session.
4. **Rule 4: Auto Square-off Before 15:20 IST**:
   - Never hold MIS intraday positions past 15:20 IST to prevent broker square-off penalties (₹50+GST per order).
5. **Rule 5: Zero-Brokerage Net Cost Accounting**:
   - Compute net realized PnL taking into account STT (0.025% on sell), NSE exchange turnover charges, SEBI fee, and GST.

---

## 3. Strategy Selection Decision Matrix

```mermaid
flowchart TD
    Start[09:15 AM Market Open] --> Scan[Scan Market Breadth & Volatility]
    Scan --> CheckTime{Current Time IST?}
    
    CheckTime -->|09:15 - 09:30| G1{Gap >= 1.5% with Catalyst?}
    G1 -->|Yes| S_Gap[Strategy 6: Gap and Go]
    G1 -->|No| S_Mom[Strategy 1: Momentum Trading]
    
    CheckTime -->|09:30 - 10:30| G2{15m OR Size <= 0.7x ATR?}
    G2 -->|Yes| S_ORB[Strategy 7: Opening Range Breakout]
    G2 -->|Too Wide / Chop| S_VWAP1[Evaluate VWAP Trend]
    
    CheckTime -->|10:30 - 13:30| G3{Tight Range Formation?}
    G3 -->|Yes: 3+ touches| S_Break[Strategy 2: Breakout Trading]
    G3 -->|Pullback to VWAP| S_VWAP[Strategy 4: VWAP Pullback Bounce]
    G3 -->|Overbought RSI > 80 + Wick| S_Rev[Strategy 3: Reversal Trading]
    
    CheckTime -->|Any Liquid Window| G4{Micro Spread == 0.05 & High Depth}| S_Scalp[Strategy 5: Scalping]
    
    CheckTime -->|>= 15:15 IST| KillSwitch[MANDATORY SQUARE OFF ALL POSITIONS]
```

---

## 4. Claude Agent Action Protocol

When Claude acts as an autonomous or semi-autonomous trading assistant:
1. **At 09:00 IST**: Run pre-market scanner, check GIFT Nifty, list gap stocks.
2. **At 09:16 IST**: Check opening candle strength; propose or execute Gap and Go or Momentum setups.
3. **At 09:30 IST**: Compute 15-minute Opening Range high and low. If valid, set alert/order triggers.
4. **Throughout Midday**: Maintain watch on VWAP pullbacks and 15m horizontal consolidation channels.
5. **At 15:15 IST**: Initiate mandatory liquidation of all open MIS positions.
6. **At 15:35 IST**: Review trade journal, verify risk adherence, log learnings.
