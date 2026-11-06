"""
Streamlit Application: NIFTY 50 Live Intraday Strategy Scanner & Trade Setup Detector.
Continuously analyzes NSE snapshots for user-selected stocks and probes
setups across enabled intraday strategies.
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
from trading_harness.market_data.snapshot_candles import synthesize_5m_candles
from trading_harness.scanner_engine import LiveScannerEngine
from trading_harness.alert_journal import TradeAlertJournal, group_alert_episodes

# -----------------------------------------------------------------------------
# Streamlit Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="NIFTY 50 Intraday Strategy Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Trading-terminal styling
st.markdown("""
<style>
    :root {
        color-scheme: dark;
        --app-bg: #080d17;
        --panel-bg: #0f1725;
        --panel-raised: #141f30;
        --panel-border: #233149;
        --text-primary: #e6edf7;
        --text-muted: #8fa0b8;
        --accent: #38bdf8;
        --positive: #34d399;
        --negative: #fb7185;
    }
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse at 12% 0%, rgba(14, 116, 144, 0.10), transparent 34%),
            var(--app-bg);
        color: var(--text-primary);
    }
    [data-testid="stHeader"] {
        background: rgba(8, 13, 23, 0.85);
    }
    [data-testid="stSidebar"] {
        background: #0b1220;
        border-right: 1px solid var(--panel-border);
    }
    [data-testid="stSidebar"] > div:first-child {
        background: transparent;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 0.45rem;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 0.45rem;
        padding-bottom: 0.75rem;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem;
    }
    [data-testid="stSidebar"] h1 {
        margin-top: 0;
        margin-bottom: 0.35rem;
    }
    [data-testid="stSidebar"] h2 {
        margin-top: 0.55rem;
        margin-bottom: 0.3rem;
    }
    .block-container {
        max-width: 1680px;
        padding-top: 1.35rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        color: var(--text-primary) !important;
        letter-spacing: -0.025em;
    }
    h2 {
        font-size: 1.18rem !important;
        font-weight: 650 !important;
    }
    p, label, [data-testid="stCaptionContainer"] {
        color: var(--text-muted);
    }
    hr {
        border-color: var(--panel-border);
        margin: 1.4rem 0;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, var(--panel-raised), var(--panel-bg));
        border: 1px solid var(--panel-border);
        border-radius: 10px;
        padding: 13px 15px;
        min-height: 82px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.68rem !important;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: var(--text-muted) !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
        font-weight: 650;
        color: var(--text-primary) !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.72rem !important;
    }
    .stButton > button {
        border: 1px solid #2b3c55;
        border-radius: 7px;
        background: #131e2e;
        color: #dce7f5;
        font-weight: 600;
        transition: border-color 120ms ease, background 120ms ease;
    }
    .stButton > button:hover {
        color: #ffffff;
        border-color: #38bdf8;
        background: #17283b;
    }
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] [data-baseweb="select"],
    [data-testid="stMultiSelect"] [data-baseweb="select"] {
        background: #101a29;
        border-color: #2b3c55;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--panel-border);
        border-radius: 9px;
        overflow: hidden;
    }
    [data-testid="stPlotlyChart"] {
        border: 1px solid var(--panel-border);
        border-radius: 10px;
        overflow: hidden;
        background: var(--panel-bg);
    }
    .terminal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 18px;
        padding: 18px 20px;
        margin: 0 0 16px;
        border: 1px solid var(--panel-border);
        border-radius: 12px;
        background: linear-gradient(110deg, #121e2e, #0d1624 70%);
        box-shadow: 0 8px 26px rgba(0, 0, 0, 0.16);
    }
    .terminal-brand {
        color: #f1f6fc;
        font-size: 1.45rem;
        font-weight: 720;
        letter-spacing: -0.035em;
    }
    .terminal-eyebrow {
        margin-bottom: 5px;
        color: #7f91aa;
        font-size: 0.64rem;
        font-weight: 700;
        letter-spacing: 0.14em;
    }
    .terminal-subtitle {
        margin-top: 4px;
        color: #91a1b7;
        font-size: 0.78rem;
    }
    .terminal-status {
        flex: 0 0 auto;
        text-align: right;
    }
    .status-pill {
        display: inline-block;
        padding: 5px 9px;
        border: 1px solid #245b4d;
        border-radius: 999px;
        background: rgba(16, 185, 129, 0.10);
        color: #6ee7b7;
        font-size: 0.68rem;
        font-weight: 750;
        letter-spacing: 0.06em;
    }
    .status-pill.closed {
        border-color: #6b512b;
        background: rgba(245, 158, 11, 0.10);
        color: #fbbf24;
    }
    .terminal-clock {
        margin-top: 7px;
        color: #a7b5c8;
        font-size: 0.73rem;
        font-variant-numeric: tabular-nums;
    }
    .main-title {
        font-size: 1.45rem;
        font-weight: 720;
        margin-bottom: 0;
        color: #f1f6fc;
    }
    .sub-title {
        color: #91a1b7;
        font-size: 0.78rem;
        margin: 4px 0 0;
    }
    .metric-card {
        background: var(--panel-bg);
        border-radius: 10px;
        padding: 12px 16px;
        border: 1px solid var(--panel-border);
    }
    .nifty-index-card {
        min-height: 82px;
        padding: 13px 15px;
        border-radius: 10px;
        background: linear-gradient(145deg, #142437, #0f1725);
        border: 1px solid #25415a;
    }
    .nifty-index-label {
        color: #8fa0b8;
        font-size: 10px;
        line-height: 1.2;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-bottom: 7px;
    }
    .nifty-index-value {
        color: #f1f6fc;
        font-size: 22px;
        font-weight: 650;
        line-height: 1.2;
        font-variant-numeric: tabular-nums;
    }
    .nifty-index-delta {
        font-size: 10px;
        line-height: 1.3;
        margin-top: 3px;
        font-weight: 650;
    }
    .setup-card-buy {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.10) 0%, #111b2a 100%);
        border: 1px solid #10b981;
        border-left: 4px solid #10b981;
        border-radius: 9px;
        padding: 16px;
        margin-bottom: 14px;
    }
    .setup-card-sell {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.10) 0%, #111b2a 100%);
        border: 1px solid #ef4444;
        border-left: 4px solid #ef4444;
        border-radius: 9px;
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
        border: 1px solid var(--panel-border);
        border-radius: 9px;
        background: #0c1421;
    }
    .trade-alert-row {
        display: grid;
        grid-template-columns: 145px minmax(100px, 1fr) 70px minmax(130px, 1.2fr) repeat(5, minmax(85px, 0.8fr));
        gap: 10px;
        align-items: center;
        padding: 9px 12px;
        border-bottom: 1px solid #1d2b3e;
        color: #cbd5e1;
        font-size: 12px;
        line-height: 1.35;
        min-width: 1030px;
    }
    .trade-alert-header {
        position: sticky;
        top: 0;
        z-index: 1;
        background: #172336;
        color: #91a1b7;
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
    @media (max-width: 720px) {
        .terminal-header { align-items: flex-start; padding: 14px; }
        .terminal-brand { font-size: 1.15rem; }
        .terminal-status { max-width: 115px; }
        .terminal-clock { font-size: 0.65rem; }
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
def get_auto_poller():
    poller = NSEAutoPoller(
        get_collector(),
        interval_seconds=300,
        maintenance_callbacks=[get_trade_alert_journal().archive_expired_files],
    )
    poller.start()
    return poller

@st.cache_resource
def get_trade_alert_journal():
    return TradeAlertJournal()


def read_trade_alert_history(journal, date_str):
    """Read history with compatibility for journals lacking read_alerts()."""
    read_alerts = getattr(journal, "read_alerts", None)
    if callable(read_alerts):
        return read_alerts(date_str)

    active_path = journal.path
    archive_dir = getattr(
        journal,
        "archive_dir",
        os.path.join(os.path.dirname(active_path), "archive"),
    )
    candidate_paths = [
        active_path,
        os.path.join(archive_dir, os.path.basename(active_path)),
    ]
    for path in candidate_paths:
        if not os.path.exists(path):
            continue
        history = pd.read_csv(path, dtype=str)
        if "snapshot_ist" in history.columns:
            history = history[
                history["snapshot_ist"].astype(str).str[:10] == date_str
            ]
        return history.to_dict("records")
    return []


collector = get_collector()
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
    "Opening Range Breakout",
    "Supply & Demand (5m)",
]

# -----------------------------------------------------------------------------
# Sidebar: Settings & Controls
# -----------------------------------------------------------------------------
st.sidebar.title("⚡ Control Panel")

ist_now = collector.get_ist_now()
is_open = collector.is_market_hours(ist_now)

# 1. Risk & Account Parameters
with st.sidebar.expander("🛡️ Risk Parameters", expanded=False):
    capital = st.number_input(
        "Account Capital (INR)",
        min_value=10000.0,
        max_value=50000000.0,
        value=100000.0,
        step=10000.0,
    )
    risk_pct_val = st.slider(
        "Risk Per Trade (%)",
        min_value=0.5,
        max_value=2.0,
        value=1.5,
        step=0.1,
    ) / 100.0
    st.caption(
        "Enforces Flattrade Rule 2: Max 1-2% risk per trade. "
        "Square-off cut-off: 15:20 IST."
    )

# 2. Strategy Toggles
selected_strategies = []
with st.sidebar.expander("🎯 Active Strategies", expanded=False):
    for strat in ALL_STRATEGIES:
        if st.checkbox(strat, value=True):
            selected_strategies.append(strat)
st.sidebar.warning(
    "Supply & Demand may generate ESTIMATED signals from sampled NSE prices. "
    "Estimated bars use endpoint prices and cumulative-volume changes; true "
    "intra-interval moves and wicks are unknown. Treat these signals as "
    "experimental, not verified trade data."
)

# 4. Live Data Actions
st.sidebar.subheader("📡 NSE Live Collector")
poll_status = auto_poller.get_status()
last_result = poll_status["last_result"]
next_poll = poll_status["next_poll_at"]
if poll_status["last_poll_at"]:
    st.sidebar.caption(
        f"Last poll: {poll_status['last_poll_at'].strftime('%H:%M:%S')} IST "
        f"({last_result['status']})"
    )
    if last_result["status"] == "ERROR":
        st.sidebar.error(f"NSE poll failed: {last_result.get('error', 'Unknown error')}")
else:
    st.sidebar.caption("Automatic polls align to 5-minute clock marks during market hours.")
if next_poll is not None:
    st.sidebar.caption(f"Next scheduled poll: {next_poll.strftime('%H:%M:%S')} IST.")

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
        archived_alerts = trade_alert_journal.archive_expired_files(include_current=True)
        if archived:
            st.success("Today's snapshot file archived to data/archive/")
        else:
            st.info("No snapshot file to archive")
        if archived_alerts:
            st.success("Today's trade-call file archived to logs/archive/")
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
daily_snapshot_path = collector.running_file_path
if not os.path.exists(daily_snapshot_path):
    archived_snapshot_path = os.path.join(
        collector.archive_dir,
        os.path.basename(daily_snapshot_path),
    )
    if os.path.exists(archived_snapshot_path):
        daily_snapshot_path = archived_snapshot_path
df_running = scanner.load_running_data(daily_snapshot_path)
if not df_running.empty and "snapshot_ist" in df_running.columns:
    today_ist = ist_now.strftime("%Y-%m-%d")
    df_running = df_running[
        df_running["snapshot_ist"].astype(str).str[:10] == today_ist
    ].copy()

# -----------------------------------------------------------------------------
# Main Dashboard Header: Trading Terminal
# -----------------------------------------------------------------------------
status_class = "" if is_open else "closed"
market_status = "MARKET OPEN" if is_open else "MARKET CLOSED"
st.markdown(
    f"<div class='terminal-header'>"
    f"<div><div class='terminal-eyebrow'>NSE • INTRADAY MARKET MONITOR</div>"
    f"<div class='terminal-brand'>NIFTY 50 Trading Desk</div>"
    f"<div class='terminal-subtitle'>Live watchlist, strategy signals, and snapshot-based technical analysis</div></div>"
    f"<div class='terminal-status'><span class='status-pill {status_class}'>{market_status}</span>"
    f"<div class='terminal-clock'>IST {ist_now.strftime('%d %b %Y · %H:%M:%S')}</div></div>"
    f"</div>",
    unsafe_allow_html=True,
)

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
        snapshot_strategies = [
            strategy for strategy in selected_strategies
            if strategy != "Supply & Demand (5m)"
        ]
        setups = scanner.scan_symbol_setups(
            series,
            sym,
            active_strategies=snapshot_strategies,
        )
        if "Supply & Demand (5m)" in selected_strategies:
            estimated_candles = synthesize_5m_candles(df_running, sym)
            if not estimated_candles.empty:
                estimated_candles.attrs["allow_estimated_ohlcv"] = True
                estimated_candles.attrs["tick_size"] = 0.05
                estimated_candles = scanner._enrich_indicators(estimated_candles)
                estimated_candles.attrs.update({
                    "data_source": "synthetic_estimate",
                    "timeframe": "5m",
                    "timezone": "Asia/Kolkata",
                    "verified_ohlcv": False,
                    "allow_estimated_ohlcv": True,
                    "tick_size": 0.05,
                })
                setups.extend(scanner.scan_symbol_setups(
                    estimated_candles,
                    sym,
                    active_strategies=["Supply & Demand (5m)"],
                ))
        symbol_snapshots = df_running.loc[
            df_running["symbol"] == sym, "snapshot_ist"
        ].dropna().astype(str)
        latest_snapshot = symbol_snapshots.max()
        for setup in setups:
            setup["timestamp"] = str(latest_snapshot)
        all_identified_setups.extend(setups)

# Sort setups: High confidence first, then best R:R
all_identified_setups.sort(key=lambda s: (s["confidence"] == "HIGH", s["rr_numeric"]), reverse=True)

alert_date = ist_now.date().isoformat()
for setup in all_identified_setups:
    trade_alert_journal.log_alert(setup)

current_alert_groups = {}
for setup in all_identified_setups:
    key = (setup["symbol"], setup["side"])
    group = current_alert_groups.get(key)
    if group is None:
        group = dict(setup)
        group["strategy_rationales"] = {
            setup["strategy"]: setup.get("rationale", "")
        }
        current_alert_groups[key] = group
        continue

    group["strategy_rationales"][setup["strategy"]] = setup.get("rationale", "")
    if (setup["confidence"] == "HIGH", setup["rr_numeric"]) > (
        group["confidence"] == "HIGH", group["rr_numeric"]
    ):
        for field in (
            "strategy", "entry_price", "stop_loss", "target", "risk_reward",
            "rr_numeric", "quantity", "max_risk_inr",
            "potential_reward_inr", "confidence",
        ):
            group[field] = setup[field]
    if setup.get("data_quality") == "ESTIMATED":
        group["data_quality"] = "ESTIMATED"

current_snapshot_alerts = sorted(
    current_alert_groups.values(),
    key=lambda setup: (setup["confidence"] == "HIGH", setup["rr_numeric"]),
    reverse=True,
)
for setup in current_snapshot_alerts:
    setup["strategies"] = sorted(setup["strategy_rationales"])
    setup["rationale"] = " | ".join(
        f"{strategy}: {rationale}"
        for strategy, rationale in sorted(setup["strategy_rationales"].items())
        if rationale
    )

history_episodes = group_alert_episodes(
    read_trade_alert_history(trade_alert_journal, alert_date)
)
active_snapshot_times = {
    (setup["symbol"], setup["side"]): pd.to_datetime(setup["timestamp"])
    for setup in current_snapshot_alerts
}
earlier_snapshot_alerts = []
for episode in history_episodes:
    active_time = active_snapshot_times.get((episode["symbol"], episode["side"]))
    episode_last_seen = pd.to_datetime(episode["last_seen"])
    if (
        active_time is not None
        and episode_last_seen <= active_time
        and active_time - episode_last_seen <= pd.Timedelta(minutes=15)
    ):
        continue
    episode["data_quality"] = (
        "ESTIMATED"
        if any(
            "ESTIMATED snapshot-derived bars" in rationale
            for rationale in episode.get("strategy_rationales", {}).values()
        )
        else "VERIFIED"
    )
    earlier_snapshot_alerts.append(episode)


def render_trade_alert_list(setups):
    rows = []
    for setup in setups:
        side_class = "trade-alert-buy" if setup["side"] == "BUY" else "trade-alert-sell"
        strategy_rationales = setup.get("strategy_rationales", {})
        strategy_names = setup.get("strategies", [setup["strategy"]])
        tooltip = "\n".join(
            f"{strategy}: {strategy_rationales.get(strategy, setup.get('rationale', ''))}"
            for strategy in strategy_names
        )
        rationale = html.escape(tooltip, quote=True)
        strategy_label = " · ".join(strategy_names)
        time_label = setup.get("start_timestamp", setup.get("timestamp", ""))
        last_seen = setup.get("last_seen")
        if last_seen and last_seen != time_label:
            time_label += f" – {last_seen[11:16]}"
        if setup.get("updates"):
            time_label += f" ({setup['updates']} updates)"
        rows.append(
            "<div class='trade-alert-row'>"
            f"<span>{html.escape(time_label)}</span>"
            f"<span class='trade-alert-symbol'>{html.escape(setup['symbol'])}</span>"
            f"<span class='{side_class}'>{html.escape(setup['side'])}</span>"
            f"<span title='{rationale}'>{html.escape(strategy_label)}"
            f"{' ⚠ ESTIMATED' if setup.get('data_quality') == 'ESTIMATED' else ''} ⓘ</span>"
            f"<span>₹{float(setup['entry_price']):,.2f}</span>"
            f"<span>₹{float(setup['stop_loss']):,.2f}</span>"
            f"<span>₹{float(setup['target']):,.2f}</span>"
            f"<span>{setup['risk_reward']}</span>"
            f"<span>{int(float(setup['quantity']))}</span>"
            "</div>"
        )

    st.markdown(
        "<div class='trade-alert-pane'>"
        "<div class='trade-alert-row trade-alert-header'>"
        "<span>Episode (IST)</span><span>Symbol</span><span>Side</span>"
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
    f"**Active setups** — latest snapshot {latest_snapshot_timestamp or 'unavailable'} "
    f"({len(current_snapshot_alerts)} symbol/direction groups)"
)
render_trade_alert_list(current_snapshot_alerts)

with st.expander(f"Setup history ({len(earlier_snapshot_alerts)} episodes)", expanded=False):
    render_trade_alert_list(earlier_snapshot_alerts)
st.caption(
    "Active calls are combined by symbol and direction; strategy names are grouped "
    "together and levels show the strongest current setup. Price-only changes are "
    "suppressed from the journal for 15 minutes; a later reappearance starts a new episode."
)
st.caption(
    f"Trade calls are recorded in `{trade_alert_journal.path}`, deduplicated by day, "
    "symbol, strategy, side, entry, and target; completed daily files move to `logs/archive/`."
)

# -----------------------------------------------------------------------------
# Interactive Technical Charting Studio (Plotly)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 Intraday Time Series & Setup Visualizer")

if selected_symbols:
    chart_symbol = st.selectbox("Select Symbol to Inspect Chart & Indicators:", options=selected_symbols, index=0)

    df_chart = synthesize_5m_candles(df_running, chart_symbol)
    if not df_chart.empty:
        df_chart = scanner._enrich_indicators(df_chart)

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            row_heights=[0.60, 0.20, 0.20],
            subplot_titles=(
                f"{chart_symbol} Estimated 5-Minute Bars with VWAP",
                "Volume & RVOL (snapshot deltas)",
                "RSI (14) — estimated closes",
            )
        )

        fig.add_trace(
            go.Candlestick(
                x=df_chart["timestamp"],
                open=df_chart["open"],
                high=df_chart["high"],
                low=df_chart["low"],
                close=df_chart["close"],
                name="Estimated 5m bar",
                increasing_line_color='#10b981',
                decreasing_line_color='#ef4444'
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["vwap"],
                line=dict(color='#f59e0b', width=2),
                name="Estimated VWAP"
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["ema9"],
                line=dict(color='#06b6d4', width=1.5, dash='dot'),
                name="9 EMA"
            ),
            row=1, col=1
        )

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
        st.caption(
            "Exploratory estimates only—not verified OHLCV or trade signals. Each bar uses "
            "the prior and current sampled LTP for open/close; high/low show only those "
            "sampled endpoints, so intra-interval moves and true wicks are unknown. Volume "
            "is the change in cumulative session volume. Missing intervals are omitted."
        )
    else:
        st.info(
            "No adjacent, clock-aligned snapshots are available yet to estimate a 5-minute bar."
        )

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
        symbol_setup = next(
            (s for s in all_identified_setups if s["symbol"] == sym),
            None,
        )
        setup_name = symbol_setup["strategy"] if symbol_setup else "-"
        if symbol_setup and symbol_setup.get("data_quality") == "ESTIMATED":
            setup_name += " (ESTIMATED)"
        
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
        }).map(
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
