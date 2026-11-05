"""
Configuration settings for the Indian Intraday Trading Harness.
Compliant with NSE/BSE market rules and Flattrade zero-brokerage structure.
"""

from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class StatutoryFeeStructure:
    """
    Statutory government and exchange levies in Indian markets (NSE/BSE).
    Reflects Flattrade's zero brokerage model.
    """
    brokerage_per_order: float = 0.0          # Flattrade charges 0 brokerage across all segments
    stt_equity_sell_pct: float = 0.00025       # 0.025% on sell turnover for equity intraday
    exchange_turnover_pct: float = 0.0000325   # NSE turnover charges (~0.00325%)
    gst_pct: float = 0.18                      # 18% GST on exchange turnover + SEBI charges
    sebi_turnover_pct: float = 0.000001        # ₹10 per crore (0.0001%)
    stamp_duty_buy_pct: float = 0.00003        # 0.003% on buy turnover for equity intraday


@dataclass
class MarketSessionConfig:
    """Session timings in Indian Standard Time (IST)"""
    pre_open_start: str = "09:00"
    pre_open_end: str = "09:08"
    market_open: str = "09:15"
    volatility_hour_end: str = "10:15"
    midday_start: str = "11:30"
    midday_end: str = "13:30"
    afternoon_resumption: str = "13:30"
    closing_hour_start: str = "14:30"
    auto_square_off_time: str = "15:20"        # Broker auto square-off cut-off
    market_close: str = "15:30"


@dataclass
class RiskConfig:
    """Core non-negotiable intraday risk limits"""
    account_capital: float = 100000.0          # Initial default capital (INR 1,00,000)
    risk_per_trade_pct: float = 0.015          # 1.5% max risk per trade (within 1-2% rule)
    max_daily_loss_pct: float = 0.03           # 3.0% maximum daily drawdown kill-switch
    max_open_positions: int = 3                # Limit active exposure
    max_leverage_mis: float = 5.0              # 5x MIS equity leverage under SEBI peak margin norms
    max_consecutive_losses: int = 3            # Cool-down trigger
    require_hard_stop_loss: bool = True        # Stop loss order is mandatory


@dataclass
class TradingHarnessConfig:
    risk: RiskConfig = field(default_factory=RiskConfig)
    session: MarketSessionConfig = field(default_factory=MarketSessionConfig)
    fees: StatutoryFeeStructure = field(default_factory=StatutoryFeeStructure)
    broker_type: str = "MOCK"                  # 'MOCK' or 'FLATTRADE'
    default_product: str = "MIS"               # Margin Intraday Square-off
    log_dir: str = "logs"
    journal_file: str = "logs/trade_journal.json"
