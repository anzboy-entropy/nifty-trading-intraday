"""
Streamlit Application: NIFTY 50 Live Intraday Strategy Scanner & Trade Setup Detector.
Continuously analyzes NSE snapshots for user-selected stocks and probes
setups across all 7 Flattrade strategies.
"""

import os
import sys
import time
import json
import html
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timezone, timedelta

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from trading_harness.market_data.nse_live_collector import NSELiveCollector
from trading_harness.market_data.nse_auto_poller import NSEAutoPoller
from trading_harness.scanner_engine import LiveScannerEngine
from trading_harness.alert_journal import TradeAlertJournal
from trading_harness.clock import IndianMarketClock

# -----------------------------------------------------------------------------
# Streamlit Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="NIFTY 50 Intraday Strategy Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-Quality Dark Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        margin-bottom: 0px;
        color: #ffffff;
    }
    .sub-title {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-bottom: 15px;
    }
    .metric-card {
        background-color: #1e293b;
        border-radius: 8px;
        padding: 12px 16px;
        border: 1px solid #334155;
    }
    .nifty-index-card {
        min-height: 78px;
        padding: 8px 12px;
        border-radius: 8px;
        background: #1e293b;
        border: 1px solid #334155;
    }
    .nifty-index-label {
        color: #94a3b8;
        font-size: 11px;
        line-height: 1.2;
        margin-bottom: 5px;
    }
    .nifty-index-value {
        color: #f8fafc;
        font-size: 21px;
        font-weight: 600;
        line-height: 1.2;
    }
    .nifty-index-delta {
        font-size: 11px;
        line-height: 1.3;
        margin-top: 3px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 11px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 19px !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 10px !important;
    }
    .setup-card-buy {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(30, 41, 59, 0.95) 100%);
        border: 1px solid #10b981;
        border-left: 6px solid #10b981;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 14px;
    }
    .setup-card-sell {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(30, 41, 59, 0.95) 100%);
        border: 1px solid #ef4444;
        border-left: 6px solid #ef4444;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 14px;
    }
    .badge-buy {
        background-color: #065f46;
        color: #34d399;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .badge-sell {
        background-color: #7f1d1d;
        color: #f87171;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .badge-strategy {
        background-color: #1e3a8a;
        color: #93c5fd;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-left: 6px;
    }
    .trade-alert-pane {
        max-height: 460px;
        overflow-y: auto;
        border: 1px solid #334155;
        border-radius: 8px;
        background: #0f172a;
    }
    .trade-alert-row {
        display: grid;
        grid-template-columns: 145px minmax(100px, 1fr) 70px minmax(130px, 1.2fr) repeat(5, minmax(85px, 0.8fr));
        gap: 10px;
        align-items: center;
        padding: 9px 12px;
        border-bottom: 1px solid #263449;
        color: #cbd5e1;
        font-size: 12px;
        line-height: 1.35;
        min-width: 1030px;
    }
    .trade-alert-header {
        position: sticky;
        top: 0;
        z-index: 1;
        background: #1e293b;
        color: #94a3b8;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
    }
    .trade-alert-symbol {
        color: #f8fafc;
        font-size: 13px;
        font-weight: 700;
    }
    .trade-alert-buy {
        color: #34d399;
        font-weight: 700;
    }
    .trade-alert-sell {
        color: #f87171;
        font-weight: 700;
    }
    .trade-alert-rationale {
        color: #94a3b8;
        white-space: normal;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Initialize Core Engines
# -----------------------------------------------------------------------------
@st.cache_resource
def get_collector():
    return NSELiveCollector()

@st.cache_resource
def get_clock():
    return IndianMarketClock()

@st.cache_resource
def get_auto_poller():
    poller = NSEAutoPoller(get_collector(), interval_seconds=300)
    poller.start()
    return poller

@st.cache_resource
def get_trade_alert_journal():
    return TradeAlertJournal()

collector = get_collector()
clock = get_clock()
auto_poller = get_auto_poller()
trade_alert_journal = get_trade_alert_journal()

# NIFTY 50 Top 10 Heavyweights Presets
HEAVYWEIGHTS = [
    "HDFCBANK", "RELIANCE", "ICICIBANK", "INFY", "ITC",
    "TCS", "LT", "SBIN", "BHARTIARTL", "BAJFINANCE"
]

ALL_STRATEGIES = [
    "Momentum Trading",
    "Breakout Trading",
    "Reversal Trading",
    "VWAP Trading",
    "Scalping",
    "Gap and Go",
    "Opening Range Breakout"
]

# -----------------------------------------------------------------------------
# Sidebar: Settings & Controls
# -----------------------------------------------------------------------------
st.sidebar.title("⚡ Control Panel")

# 1. Market Status Indicator
ist_now = collector.get_ist_now()
session_phase = clock.get_session_phase()
is_open = collector.is_market_hours(ist_now)

phase_color = "#10b981" if is_open else "#f59e0b"
st.sidebar.markdown(f"""
<div style='background-color: #0f172a; padding: 10px; border-radius: 6px; border: 1px solid #334155; margin-bottom: 12px;'>
    <div style='font-size: 0.8rem; color: #94a3b8;'>INDIAN STANDARD TIME (IST)</div>
    <div style='font-size: 1.1rem; font-weight: 700; color: #f8fafc;'>{ist_now.strftime('%H:%M:%S')}</div>
    <div style='font-size: 0.8rem; color: {phase_color}; font-weight: 600;'>● {session_phase.replace('_', ' ')} {'(OPEN)' if is_open else '(CLOSED)'}</div>
</div>
""", unsafe_allow_html=True)

# 2. Risk & Account Parameters
st.sidebar.subheader("🛡️ Risk Parameters")
capital = st.sidebar.number_input("Account Capital (INR)", min_value=10000.0, max_value=50000000.0, value=100000.0, step=10000.0)
risk_pct_val = st.sidebar.slider("Risk Per Trade (%)", min_value=0.5, max_value=2.0, value=1.5, step=0.1) / 100.0

st.sidebar.caption("Enforces Flattrade Rule 2: Max 1-2% risk per trade. Square-off cut-off: 15:20 IST.")

# 3. Strategy Toggles
st.sidebar.subheader("🎯 Active Strategies")
selected_strategies = []
for strat in ALL_STRATEGIES:
    if st.sidebar.checkbox(strat, value=True):
        selected_strategies.append(strat)

# 4. Live Data Actions
st.sidebar.subheader("📡 NSE Live Collector")
poll_status = auto_poller.get_status()
last_result = poll_status["last_result"]
if poll_status["last_poll_at"]:
    st.sidebar.caption(
        f"Last poll: {poll_status['last_poll_at'].strftime('%H:%M:%S')} IST "
        f"({last_result['status']})"
    )
    if last_result["status"] == "ERROR":
        st.sidebar.error(f"NSE poll failed: {last_result.get('error', 'Unknown error')}")
    elif last_result["status"] == "SUCCESS":
        next_poll = poll_status["next_poll_at"]
        if next_poll is not None:
            seconds_remaining = max(0, int(next_poll - time.monotonic()))
            st.sidebar.caption(
                f"Automatic polling every 5 minutes during market hours. "
                f"Next poll in about {seconds_remaining // 60}m {seconds_remaining % 60}s."
            )
else:
    st.sidebar.caption("Automatic polling every 5 minutes during market hours.")

col_b1, col_b2 = st.sidebar.columns(2)
with col_b1:
    if st.button("🔄 Poll NSE", help="Fetches an immediate live snapshot from NSE website"):
        with st.spinner("Fetching from NSE..."):
            res = auto_poller.poll_now(force=True)
            if res.get("status") == "SUCCESS":
                st.success("Snapshot saved!")
            else:
                st.error(f"NSE fetch error: {res.get('error', res.get('message', res['status']))}")
            st.rerun()

with col_b2:
    if st.button("📦 Archive EOD", help="Archives the running file to data/archive/"):
        archived = auto_poller.archive_now()
        if archived:
            st.success("Archived to data/archive/")
        else:
            st.info("No file to archive")
        st.rerun()

# 5. Auto-Refresh Controls
with st.sidebar.expander("Dashboard refresh", expanded=False):
    auto_refresh = st.checkbox("Auto-Refresh UI", value=True, key="dashboard_auto_refresh")
    refresh_interval = st.selectbox(
        "Refresh Interval",
        options=[10, 30, 60, 180],
        index=1,
        format_func=lambda seconds: f"Every {seconds} seconds",
        key="dashboard_refresh_interval",
    )

# Load running data
scanner = LiveScannerEngine(capital=capital, risk_pct=risk_pct_val)
df_running = scanner.load_running_data()
if not df_running.empty and "snapshot_ist" in df_running.columns:
    today_ist = ist_now.strftime("%Y-%m-%d")
    df_running = df_running[
        df_running["snapshot_ist"].astype(str).str[:10] == today_ist
    ].copy()

# -----------------------------------------------------------------------------
# Main Dashboard Header: Index Ticker Banner
# -----------------------------------------------------------------------------
st.markdown("<div class='main-title'>📈 NIFTY 50 Intraday Strategy Scanner</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Probing NSE snapshot series against 7 institutional intraday strategies</div>", unsafe_allow_html=True)

if df_running.empty:
    st.warning("⚠️ No data in running file yet. The app polls NSE automatically every five minutes during market hours; you can also click **'Poll NSE'** to fetch immediately.")
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()
    st.stop()

# Extract Index Row & Stocks list
index_df = df_running[df_running["symbol"] == "NIFTY 50"]
if not index_df.empty:
    idx_row = index_df.iloc[-1]
    nifty_ltp = float(idx_row["last_price"])
    nifty_change = float(idx_row["change"])
    nifty_pchange = float(idx_row["p_change"])
    nifty_high = float(idx_row["day_high"])
    nifty_low = float(idx_row["day_low"])
else:
    nifty_ltp, nifty_change, nifty_pchange, nifty_high, nifty_low = 23960.0, 0.0, 0.0, 23960.0, 23960.0

# Top Index Metrics Banner
m1, m2, m3, m4 = st.columns(4)
nifty_delta_color = "#34d399" if nifty_change >= 0 else "#f87171"
m1.markdown(
    f"<div class='nifty-index-card'>"
    f"<div class='nifty-index-label'>NIFTY 50 INDEX</div>"
    f"<div class='nifty-index-value'>₹{nifty_ltp:,.2f}</div>"
    f"<div class='nifty-index-delta' style='color:{nifty_delta_color}'>"
    f"{nifty_change:+,.2f} ({nifty_pchange:+0.2f}%)</div></div>",
    unsafe_allow_html=True,
)
m2.metric("DAY HIGH", f"₹{nifty_high:,.2f}")
m3.metric("DAY LOW", f"₹{nifty_low:,.2f}")
m4.metric("TODAY'S SNAPSHOTS", f"{df_running['snapshot_ist'].nunique()}")

# -----------------------------------------------------------------------------
# Stock Selection & Watchlist Manager
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🔍 Select Watchlist Constituents")

# Extract unique symbols from running data
all_available_symbols = sorted(df_running["symbol"].unique().tolist())
if "NIFTY 50" in all_available_symbols:
    all_available_symbols.remove("NIFTY 50")
    all_available_symbols = ["NIFTY 50"] + all_available_symbols

# Quick Selection Buttons
col_w1, col_w2, col_w3, col_w4 = st.columns([1.5, 2, 1.5, 1])
if "selected_symbols" not in st.session_state:
    st.session_state.selected_symbols = ["NIFTY 50"] + HEAVYWEIGHTS[:5]

with col_w1:
    if st.button("✅ Select All 50 + Index"):
        st.session_state.selected_symbols = all_available_symbols
        st.rerun()

with col_w2:
    if st.button("⭐ Top 10 Heavyweights + Index"):
        st.session_state.selected_symbols = ["NIFTY 50"] + [s for s in HEAVYWEIGHTS if s in all_available_symbols]
        st.rerun()

with col_w3:
    if st.button("📊 NIFTY 50 Index Only"):
        st.session_state.selected_symbols = ["NIFTY 50"]
        st.rerun()

with col_w4:
    if st.button("❌ Clear All"):
        st.session_state.selected_symbols = []
        st.rerun()

# Multi-select Box
selected_symbols = st.multiselect(
    "Choose Stocks to Probe for Setups:",
    options=all_available_symbols,
    default=st.session_state.selected_symbols,
    help="Select the specific stocks you are interested in analyzing."
)
st.session_state.selected_symbols = selected_symbols

# -----------------------------------------------------------------------------
# Strategy Scanner Engine: Probing Selected Stocks
# -----------------------------------------------------------------------------
all_identified_setups = []
symbol_series_cache = {}
latest_snapshot_timestamp = (
    str(df_running["snapshot_ist"].dropna().astype(str).max())
    if not df_running.empty and "snapshot_ist" in df_running.columns
    else None
)

for sym in selected_symbols:
    series = scanner.get_symbol_time_series(df_running, sym)
    if not series.empty:
        symbol_series_cache[sym] = series
        setups = scanner.scan_symbol_setups(series, sym, active_strategies=selected_strategies)
        symbol_snapshots = df_running.loc[
            df_running["symbol"] == sym, "snapshot_ist"
        ].dropna().astype(str)
        latest_snapshot = symbol_snapshots.max()
        for setup in setups:
            setup["timestamp"] = str(latest_snapshot)
        all_identified_setups.extend(setups)

# Sort setups: High confidence first, then best R:R
all_identified_setups.sort(key=lambda s: (s["confidence"] == "HIGH", s["rr_numeric"]), reverse=True)

# Keep the first snapshot of each distinct setup for the current trading day.
# Changed entry or target prices create a separate alert.
alert_date = ist_now.date().isoformat()
if st.session_state.get("trade_alert_date") != alert_date:
    st.session_state.trade_alert_date = alert_date
    st.session_state.trade_alerts = {}
elif "trade_alerts" not in st.session_state:
    st.session_state.trade_alerts = {}

for setup in all_identified_setups:
    alert_key = (
        setup["symbol"],
        setup["strategy"],
        setup["side"],
        round(setup["entry_price"], 2),
        round(setup["target"], 2),
    )
    st.session_state.trade_alerts.setdefault(alert_key, dict(setup))
    trade_alert_journal.log_alert(st.session_state.trade_alerts[alert_key])

trade_alerts = sorted(
    st.session_state.trade_alerts.values(),
    key=lambda setup: (setup["confidence"] == "HIGH", setup["rr_numeric"]),
    reverse=True,
)
current_snapshot_alerts = [
    setup for setup in trade_alerts
    if setup["timestamp"] == latest_snapshot_timestamp
]
earlier_snapshot_alerts = sorted(
    (
        setup for setup in trade_alerts
        if setup["timestamp"] != latest_snapshot_timestamp
    ),
    key=lambda setup: setup["timestamp"],
    reverse=True,
)


def render_trade_alert_list(setups):
    rows = []
    for setup in setups:
        side_class = "trade-alert-buy" if setup["side"] == "BUY" else "trade-alert-sell"
        rationale = html.escape(setup.get("rationale", ""), quote=True)
        rows.append(
            "<div class='trade-alert-row'>"
            f"<span>{html.escape(setup['timestamp'])}</span>"
            f"<span class='trade-alert-symbol'>{html.escape(setup['symbol'])}</span>"
            f"<span class='{side_class}'>{html.escape(setup['side'])}</span>"
            f"<span title='{rationale}'>{html.escape(setup['strategy'])} ⓘ</span>"
            f"<span>₹{setup['entry_price']:,.2f}</span>"
            f"<span>₹{setup['stop_loss']:,.2f}</span>"
            f"<span>₹{setup['target']:,.2f}</span>"
            f"<span>{setup['risk_reward']}</span>"
            f"<span>{setup['quantity']}</span>"
            "</div>"
        )

    st.markdown(
        "<div class='trade-alert-pane'>"
        "<div class='trade-alert-row trade-alert-header'>"
        "<span>Snapshot time (IST)</span><span>Symbol</span><span>Side</span>"
        "<span>Strategy</span><span>Entry</span><span>Stop loss</span>"
        "<span>Target</span><span>Risk:Reward</span><span>Quantity</span>"
        "</div>"
        + ("".join(rows) if rows else
           "<div style='padding:12px;color:#94a3b8;font-size:12px;'>No trade setups in this list.</div>")
        + "</div>",
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# Trade Setup Alerts Section (The Core Feature)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🎯 Trade Setup Recommendations")
st.markdown(
    f"**Current snapshot** — {latest_snapshot_timestamp or 'No snapshot available'} "
    f"({len(current_snapshot_alerts)} setups)"
)
render_trade_alert_list(current_snapshot_alerts)

st.markdown(
    f"**Earlier snapshots** — newest first ({len(earlier_snapshot_alerts)} setups)"
)
render_trade_alert_list(earlier_snapshot_alerts)
st.caption("Identical calls keep their original snapshot time and details; changed entry or target values are separate alerts. Hover over a strategy to read its rationale.")
st.caption("Trade calls are recorded in `logs/trade_alerts.csv`, deduplicated by day, symbol, strategy, side, entry, and target.")

# -----------------------------------------------------------------------------
# Interactive Technical Charting Studio (Plotly)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 Intraday Time Series & Setup Visualizer")

if selected_symbols:
    chart_symbol = st.selectbox("Select Symbol to Inspect Chart & Indicators:", options=selected_symbols, index=0)
    
    if chart_symbol in symbol_series_cache:
        df_chart = symbol_series_cache[chart_symbol]
        
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            row_heights=[0.60, 0.20, 0.20],
            subplot_titles=(f"{chart_symbol} Snapshot-Based Price Estimate with VWAP", "Volume & RVOL", "RSI (14)")
        )

        # 1. Candlestick Trace
        fig.add_trace(
            go.Candlestick(
                x=df_chart["timestamp"],
                open=df_chart["open"],
                high=df_chart["high"],
                low=df_chart["low"],
                close=df_chart["close"],
                name="Snapshot estimate",
                increasing_line_color='#10b981',
                decreasing_line_color='#ef4444'
            ),
            row=1, col=1
        )

        # 2. VWAP Line
        fig.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["vwap"],
                line=dict(color='#f59e0b', width=2),
                name="VWAP (Fair Value)"
            ),
            row=1, col=1
        )

        # 3. 9 EMA Line
        fig.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["ema9"],
                line=dict(color='#06b6d4', width=1.5, dash='dot'),
                name="9 EMA"
            ),
            row=1, col=1
        )

        # Check if symbol has an identified setup to overlay entry, SL, Target
        matching_setup = next((s for s in all_identified_setups if s["symbol"] == chart_symbol), None)
        if matching_setup:
            entry_p = matching_setup["entry_price"]
            sl_p = matching_setup["stop_loss"]
            tgt_p = matching_setup["target"]

            # Add Entry Line
            fig.add_hline(y=entry_p, line_dash="solid", line_color="#3b82f6", annotation_text=f"Entry: ₹{entry_p}", row=1, col=1)
            # Add Stop Loss Line
            fig.add_hline(y=sl_p, line_dash="dash", line_color="#ef4444", annotation_text=f"SL: ₹{sl_p}", row=1, col=1)
            # Add Target Line
            fig.add_hline(y=tgt_p, line_dash="dash", line_color="#10b981", annotation_text=f"Target: ₹{tgt_p}", row=1, col=1)

        # 4. Volume Bars
        colors = ['#10b981' if c >= o else '#ef4444' for c, o in zip(df_chart["close"], df_chart["open"])]
        fig.add_trace(
            go.Bar(
                x=df_chart["timestamp"],
                y=df_chart["volume"],
                marker_color=colors,
                name="Volume"
            ),
            row=2, col=1
        )

        # 5. RSI Trace & Threshold Bands
        fig.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["rsi"],
                line=dict(color='#a855f7', width=2),
                name="RSI 14"
            ),
            row=3, col=1
        )
        fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", row=3, col=1)
        fig.add_hline(y=60, line_dash="dot", line_color="#34d399", row=3, col=1)
        fig.add_hline(y=40, line_dash="dot", line_color="#f87171", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#10b981", row=3, col=1)

        fig.update_layout(
            template="plotly_dark",
            height=650,
            xaxis_rangeslider_visible=False,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# Selected Constituents Live Market Table
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📋 Selected Constituents Live Table")

table_rows = []
for sym in selected_symbols:
    sym_rows = df_running[df_running["symbol"] == sym]
    if not sym_rows.empty:
        last = sym_rows.iloc[-1]
        has_setup = any(s["symbol"] == sym for s in all_identified_setups)
        setup_name = next((s["strategy"] for s in all_identified_setups if s["symbol"] == sym), "-")
        
        table_rows.append({
            "Symbol": sym,
            "Company": last.get("company_name", sym),
            "LTP (₹)": float(last["last_price"]),
            "Change (₹)": float(last["change"]),
            "Change (%)": float(last["p_change"]),
            "Day High (₹)": float(last["day_high"]),
            "Day Low (₹)": float(last["day_low"]),
            "Volume": int(last["volume"]),
            "Trade Signal": f"⚡ {setup_name}" if has_setup else "Watching"
        })

if table_rows:
    df_table = pd.DataFrame(table_rows)
    st.dataframe(
        df_table.style.format({
            "LTP (₹)": "₹{:,.2f}",
            "Change (₹)": "{:+,.2f}",
            "Change (%)": "{:+0.2f}%",
            "Day High (₹)": "₹{:,.2f}",
            "Day Low (₹)": "₹{:,.2f}",
            "Volume": "{:,}"
        }).applymap(
            lambda v: "color: #10b981; font-weight: bold;" if "+" in str(v) else ("color: #ef4444; font-weight: bold;" if "-" in str(v) else ""),
            subset=["Change (%)", "Change (₹)"]
        ),
        use_container_width=True,
        hide_index=True
    )

# -----------------------------------------------------------------------------
# Auto-Refresh Loop
# -----------------------------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
