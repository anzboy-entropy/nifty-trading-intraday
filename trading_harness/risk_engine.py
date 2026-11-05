"""
Intraday Risk Engine for Indian Markets.
Enforces non-negotiable risk limits: 1-2% capital risk, MIS margin check,
hard stop-loss mandate, 15:20 IST square-off, and zero-brokerage statutory costs.
"""

from typing import Dict, Any, Tuple
import math
from .config import RiskConfig, StatutoryFeeStructure
from .clock import IndianMarketClock

class RiskEngine:
    def __init__(self, risk_config: RiskConfig, fee_structure: StatutoryFeeStructure, clock: IndianMarketClock):
        self.config = risk_config
        self.fees = fee_structure
        self.clock = clock
        self.daily_kill_switch_activated = False

    def calculate_position_size(self, capital: float, entry: float, stop_loss: float, risk_pct: float = None) -> int:
        """
        Calculates position size using the 1% to 2% capital risk rule:
        Quantity = floor((Capital * Risk_Pct) / |Entry - StopLoss|)
        """
        if risk_pct is None:
            risk_pct = self.config.risk_per_trade_pct

        risk_pct = min(risk_pct, 0.02) # Hard ceiling at 2% risk
        
        per_share_risk = abs(entry - stop_loss)
        if per_share_risk <= 0.001:
            return 0
            
        max_rupee_risk = capital * risk_pct
        quantity = int(max_rupee_risk / per_share_risk)
        
        # Check SEBI MIS margin limit (max leverage 5x on intraday equities)
        max_allowed_shares = int((capital * self.config.max_leverage_mis) / entry) if entry > 0 else 0
        final_qty = min(quantity, max_allowed_shares)
        
        return max(0, final_qty)

    def validate_order(self, order: Dict[str, Any], account_state: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates order against all institutional risk rules before submission to broker.
        Returns: (is_valid, rejection_reason)
        """
        # 1. Kill Switch Check
        if self.daily_kill_switch_activated:
            return False, "Order Rejected: Daily Drawdown Kill-Switch is ACTIVE. No further trades allowed today."

        # 2. Time Window Check (Square-off time 15:20 IST)
        if self.clock.is_square_off_time():
            return False, f"Order Rejected: Market time ({self.clock.current_time_str()} IST) is at or past MIS auto square-off threshold (15:20 IST)."

        if not self.clock.is_market_open():
            return False, f"Order Rejected: Market is closed (Current IST: {self.clock.current_time_str()})."

        # 3. Product Type Validation
        product = order.get("product", "MIS").upper()
        if product != "MIS":
            return False, f"Order Rejected: Intraday harness requires 'MIS' product type, got '{product}'."

        # 4. Mandatory Hard Stop-Loss Check
        stop_loss = order.get("stop_loss")
        entry = order.get("price")
        side = order.get("side", "").upper()
        
        if self.config.require_hard_stop_loss:
            if stop_loss is None or stop_loss <= 0:
                return False, "Order Rejected: Mandatory Hard Stop-Loss is missing. Rule 1 strictly forbids naked trades."

            if side == "BUY" and stop_loss >= entry:
                return False, f"Order Rejected: Buy Stop-Loss ({stop_loss}) must be strictly below Entry price ({entry})."
            elif side == "SELL" and stop_loss <= entry:
                return False, f"Order Rejected: Sell (Short) Stop-Loss ({stop_loss}) must be strictly above Entry price ({entry})."

        # 5. Risk-per-trade cap (<= 2% of capital)
        qty = order.get("quantity", 0)
        if qty <= 0:
            return False, "Order Rejected: Order quantity must be greater than zero."
            
        trade_risk_amount = abs(entry - stop_loss) * qty
        max_allowed_risk = account_state["capital"] * 0.0205 # 2% buffer
        
        if trade_risk_amount > max_allowed_risk:
            return False, f"Order Rejected: Risk amount (INR {trade_risk_amount:.2f}) exceeds 2% capital limit (INR {max_allowed_risk:.2f})."

        # 6. Max Concurrent Open Positions
        open_positions = account_state.get("open_positions_count", 0)
        if open_positions >= self.config.max_open_positions:
            return False, f"Order Rejected: Max open positions limit reached ({self.config.max_open_positions})."

        # 7. Check Daily Drawdown Limit (3%)
        realized_pnl = account_state.get("realized_pnl", 0.0)
        unrealized_pnl = account_state.get("unrealized_pnl", 0.0)
        total_pnl = realized_pnl + unrealized_pnl
        max_loss_rupees = account_state["capital"] * self.config.max_daily_loss_pct
        
        if total_pnl <= -max_loss_rupees:
            self.daily_kill_switch_activated = True
            return False, f"Order Rejected: Total drawdown (INR {total_pnl:.2f}) breached 3% max daily limit (INR {max_loss_rupees:.2f}). Kill-switch triggered."

        return True, "Order Approved by Risk Engine"

    def calculate_statutory_charges(self, side: str, price: float, quantity: int) -> Dict[str, float]:
        """
        Calculates exact statutory charges for Indian equity intraday (Flattrade Zero Brokerage model).
        """
        turnover = round(price * quantity, 2)
        brokerage = 0.0 # Flattrade ₹0 brokerage
        
        # STT: 0.025% on sell side only
        stt = round(turnover * self.fees.stt_equity_sell_pct, 2) if side.upper() == "SELL" else 0.0
        
        # Stamp duty: 0.003% on buy side only
        stamp_duty = round(turnover * self.fees.stamp_duty_buy_pct, 2) if side.upper() == "BUY" else 0.0
        
        # Exchange turnover charge: 0.00325%
        exchange_turnover = round(turnover * self.fees.exchange_turnover_pct, 2)
        
        # SEBI Turnover fee: ₹10/crore
        sebi_fee = round(turnover * self.fees.sebi_turnover_pct, 2)
        
        # GST: 18% on (Brokerage + Exchange Turnover + SEBI Fee)
        taxable_services = brokerage + exchange_turnover + sebi_fee
        gst = round(taxable_services * self.fees.gst_pct, 2)
        
        total_charges = round(brokerage + stt + stamp_duty + exchange_turnover + sebi_fee + gst, 2)
        
        return {
            "turnover": turnover,
            "brokerage": brokerage,
            "stt": stt,
            "stamp_duty": stamp_duty,
            "exchange_charges": exchange_turnover,
            "sebi_charges": sebi_fee,
            "gst": gst,
            "total_charges": total_charges
        }
