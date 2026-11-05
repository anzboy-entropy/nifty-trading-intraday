"""
Mock Broker implementation for realistic paper trading and strategy testing.
Simulates order books, fills, slippage, stop loss triggers, and statutory charges.
"""

from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
from .base import BaseBroker
from ..risk_engine import RiskEngine
from ..clock import IndianMarketClock

class MockBroker(BaseBroker):
    def __init__(self, initial_capital: float, risk_engine: RiskEngine, clock: IndianMarketClock, market_data: Optional[Any] = None):
        self.capital = initial_capital
        self.available_cash = initial_capital
        self.risk_engine = risk_engine
        self.clock = clock
        self.market_data = market_data
        
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.ltp_table: Dict[str, float] = {}
        self.realized_pnl: float = 0.0
        self.total_statutory_charges: float = 0.0

    def update_ltp(self, symbol: str, price: float):
        """Updates simulated market price for symbol"""
        self.ltp_table[symbol] = price
        self._check_stop_losses_and_targets(symbol, price)

    def get_ltp(self, symbol: str) -> float:
        if symbol in self.ltp_table:
            return self.ltp_table[symbol]
        if self.market_data is not None:
            return self.market_data.get_ltp(symbol)
        return 100.0

    def get_account_state(self) -> Dict[str, Any]:
        """Calculates current account state, margin, and unrealized PnL"""
        unrealized = 0.0
        for sym, pos in self.positions.items():
            current_price = self.get_ltp(sym)
            qty = pos["quantity"]
            avg_price = pos["avg_price"]
            if pos["side"] == "BUY":
                unrealized += (current_price - avg_price) * qty
            else: # SHORT SELL
                unrealized += (avg_price - current_price) * qty
                
        return {
            "capital": self.capital,
            "available_cash": round(self.available_cash, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_pnl": round(self.realized_pnl + unrealized, 2),
            "total_statutory_charges": round(self.total_statutory_charges, 2),
            "open_positions_count": len([p for p in self.positions.values() if p["quantity"] > 0])
        }

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates order against RiskEngine and simulates exchange execution.
        """
        account_state = self.get_account_state()
        is_valid, reason = self.risk_engine.validate_order(order, account_state)
        
        order_id = f"ORD_{uuid.uuid4().hex[:8].upper()}"
        timestamp = self.clock.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not is_valid:
            rejected_order = {
                **order,
                "order_id": order_id,
                "status": "REJECTED",
                "rejection_reason": reason,
                "timestamp": timestamp
            }
            self.orders[order_id] = rejected_order
            return rejected_order

        # Execution Fill simulation
        symbol = order["symbol"]
        side = order["side"].upper()
        quantity = int(order["quantity"])
        requested_price = float(order.get("price", self.get_ltp(symbol)))
        self.ltp_table[symbol] = requested_price
        stop_loss = float(order.get("stop_loss"))
        target = float(order.get("target", 0.0))
        strategy = order.get("strategy", "generic")
        
        # Calculate entry statutory charges
        charges = self.risk_engine.calculate_statutory_charges(side, requested_price, quantity)
        self.total_statutory_charges += charges["total_charges"]
        
        filled_order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "product": "MIS",
            "quantity": quantity,
            "price": requested_price,
            "stop_loss": stop_loss,
            "target": target,
            "strategy": strategy,
            "status": "COMPLETE",
            "charges": charges,
            "timestamp": timestamp
        }
        self.orders[order_id] = filled_order

        # Update position
        if symbol not in self.positions or self.positions[symbol]["quantity"] == 0:
            self.positions[symbol] = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "avg_price": requested_price,
                "stop_loss": stop_loss,
                "target": target,
                "strategy": strategy,
                "entry_time": timestamp
            }
        else:
            # Position already open
            pos = self.positions[symbol]
            if pos["side"] == side:
                # Add to position
                total_qty = pos["quantity"] + quantity
                new_avg = ((pos["avg_price"] * pos["quantity"]) + (requested_price * quantity)) / total_qty
                pos["quantity"] = total_qty
                pos["avg_price"] = round(new_avg, 2)
            else:
                # Opposing side: reduce or square off
                if quantity >= pos["quantity"]:
                    # Closed completely
                    close_qty = pos["quantity"]
                    pnl = (requested_price - pos["avg_price"]) * close_qty if pos["side"] == "BUY" else (pos["avg_price"] - requested_price) * close_qty
                    self.realized_pnl += pnl
                    pos["quantity"] = 0
                else:
                    pos["quantity"] -= quantity
                    
        return filled_order

    def _check_stop_losses_and_targets(self, symbol: str, current_price: float):
        """Automatically checks if any open position's SL or Target was breached"""
        if symbol not in self.positions or self.positions[symbol]["quantity"] <= 0:
            return

        pos = self.positions[symbol]
        side = pos["side"]
        sl = pos["stop_loss"]
        target = pos["target"]
        qty = pos["quantity"]

        exit_triggered = False
        exit_reason = ""
        exit_price = current_price

        if side == "BUY":
            if current_price <= sl:
                exit_triggered = True
                exit_reason = "STOP_LOSS_HIT"
                exit_price = sl
            elif target > 0 and current_price >= target:
                exit_triggered = True
                exit_reason = "TARGET_HIT"
                exit_price = target
        elif side == "SELL":
            if current_price >= sl:
                exit_triggered = True
                exit_reason = "STOP_LOSS_HIT"
                exit_price = sl
            elif target > 0 and current_price <= target:
                exit_triggered = True
                exit_reason = "TARGET_HIT"
                exit_price = target

        if exit_triggered:
            self._close_position(symbol, exit_price, qty, exit_reason)

    def _close_position(self, symbol: str, exit_price: float, quantity: int, reason: str):
        pos = self.positions.get(symbol)
        if not pos or pos["quantity"] <= 0:
            return

        exit_side = "SELL" if pos["side"] == "BUY" else "BUY"
        gross_pnl = (exit_price - pos["avg_price"]) * quantity if pos["side"] == "BUY" else (pos["avg_price"] - exit_price) * quantity
        
        # Calculate exit statutory charges
        charges = self.risk_engine.calculate_statutory_charges(exit_side, exit_price, quantity)
        self.total_statutory_charges += charges["total_charges"]
        net_pnl = round(gross_pnl - charges["total_charges"], 2)
        
        self.realized_pnl += net_pnl
        pos["quantity"] = 0
        
        exit_order_id = f"EXIT_{uuid.uuid4().hex[:8].upper()}"
        exit_order = {
            "order_id": exit_order_id,
            "symbol": symbol,
            "side": exit_side,
            "product": "MIS",
            "quantity": quantity,
            "price": exit_price,
            "status": "COMPLETE",
            "reason": reason,
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": net_pnl,
            "charges": charges,
            "timestamp": self.clock.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.orders[exit_order_id] = exit_order

    def square_off_all(self, reason: str = "MANUAL") -> List[Dict[str, Any]]:
        """Square off all open positions immediately (e.g. at 15:20 IST)"""
        closed_orders = []
        for symbol, pos in list(self.positions.items()):
            if pos["quantity"] > 0:
                current_price = self.get_ltp(symbol)
                self._close_position(symbol, current_price, pos["quantity"], reason)
                closed_orders.append({
                    "symbol": symbol,
                    "closed_price": current_price,
                    "reason": reason
                })
        return closed_orders

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        if order_id in self.orders:
            self.orders[order_id]["status"] = "CANCELLED"
            return {"order_id": order_id, "status": "CANCELLED"}
        return {"error": "Order not found"}

    def modify_order(self, order_id: str, new_price: Optional[float] = None, 
                     new_quantity: Optional[int] = None, new_trigger_price: Optional[float] = None) -> Dict[str, Any]:
        if order_id in self.orders:
            order = self.orders[order_id]
            if new_price is not None:
                order["price"] = new_price
            if new_quantity is not None:
                order["quantity"] = new_quantity
            if new_trigger_price is not None:
                order["stop_loss"] = new_trigger_price
            return {"order_id": order_id, "status": "MODIFIED", "order": order}
        return {"error": "Order not found"}

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.positions.values())

    def get_orders(self) -> List[Dict[str, Any]]:
        return list(self.orders.values())
