"""
Trade Journal Engine for Indian Intraday Strategies.
Complies with Flattrade Rule 5: 'Keep a Trading Journal. Write down every trade –
entry, exit, reason, outcome. Review weekly.'
"""

import json
import csv
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

class TradeJournal:
    def __init__(self, journal_path: str = "logs/trade_journal.json", csv_path: str = "logs/trade_journal.csv"):
        self.journal_path = journal_path
        self.csv_path = csv_path
        self.trades: List[Dict[str, Any]] = []
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def _load(self):
        if os.path.exists(self.journal_path):
            try:
                with open(self.journal_path, "r", encoding="utf-8") as f:
                    self.trades = json.load(f)
            except Exception:
                self.trades = []

    def log_trade(self, trade_data: Dict[str, Any]):
        """
        Logs a completed intraday trade with all analytics.
        """
        entry_price = float(trade_data.get("entry_price", 0.0))
        exit_price = float(trade_data.get("exit_price", 0.0))
        quantity = int(trade_data.get("quantity", 0))
        side = trade_data.get("side", "BUY").upper()
        stop_loss = float(trade_data.get("stop_loss", 0.0))
        charges = float(trade_data.get("statutory_charges", 0.0))
        
        gross_pnl = (exit_price - entry_price) * quantity if side == "BUY" else (entry_price - exit_price) * quantity
        net_pnl = round(gross_pnl - charges, 2)
        
        # Risk multiple (R achieved)
        planned_risk = abs(entry_price - stop_loss) * quantity if stop_loss > 0 else 1.0
        r_multiple = round(net_pnl / planned_risk, 2) if planned_risk > 0 else 0.0

        record = {
            "trade_id": trade_data.get("trade_id", f"TRD_{len(self.trades) + 1:04d}"),
            "timestamp": trade_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "symbol": trade_data.get("symbol"),
            "strategy": trade_data.get("strategy"),
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "stop_loss": stop_loss,
            "target": trade_data.get("target", 0.0),
            "exit_reason": trade_data.get("exit_reason", "NORMAL"),
            "gross_pnl": round(gross_pnl, 2),
            "statutory_charges": round(charges, 2),
            "net_pnl": net_pnl,
            "r_multiple": r_multiple,
            "is_win": net_pnl > 0,
            "rationale": trade_data.get("rationale", "")
        }
        
        self.trades.append(record)
        self._save()

    def _save(self):
        with open(self.journal_path, "w", encoding="utf-8") as f:
            json.dump(self.trades, f, indent=2)

        # Also write/append to CSV
        fieldnames = [
            "trade_id", "timestamp", "symbol", "strategy", "side", "quantity",
            "entry_price", "exit_price", "stop_loss", "target", "exit_reason",
            "gross_pnl", "statutory_charges", "net_pnl", "r_multiple", "is_win", "rationale"
        ]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for t in self.trades:
                writer.writerow(t)

    def get_eod_summary(self) -> Dict[str, Any]:
        """Calculates End-of-Day trading performance review"""
        if not self.trades:
            return {
                "total_trades": 0,
                "net_pnl": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0
            }
            
        total = len(self.trades)
        wins = [t for t in self.trades if t["is_win"]]
        losses = [t for t in self.trades if not t["is_win"]]
        
        gross_profit = sum(t["net_pnl"] for t in wins)
        gross_loss = abs(sum(t["net_pnl"] for t in losses))
        net_pnl = round(sum(t["net_pnl"] for t in self.trades), 2)
        total_charges = round(sum(t["statutory_charges"] for t in self.trades), 2)
        
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        win_rate = round((len(wins) / total) * 100.0, 2)
        
        strategy_breakdown = {}
        for t in self.trades:
            s = t["strategy"]
            if s not in strategy_breakdown:
                strategy_breakdown[s] = {"trades": 0, "net_pnl": 0.0, "wins": 0}
            strategy_breakdown[s]["trades"] += 1
            strategy_breakdown[s]["net_pnl"] += t["net_pnl"]
            if t["is_win"]:
                strategy_breakdown[s]["wins"] += 1

        for s in strategy_breakdown:
            strategy_breakdown[s]["net_pnl"] = round(strategy_breakdown[s]["net_pnl"], 2)
            strategy_breakdown[s]["win_rate"] = round((strategy_breakdown[s]["wins"] / strategy_breakdown[s]["trades"]) * 100, 1)

        return {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": win_rate,
            "net_pnl_inr": net_pnl,
            "total_charges_inr": total_charges,
            "profit_factor": profit_factor,
            "strategy_breakdown": strategy_breakdown
        }
