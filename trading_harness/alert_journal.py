"""Persistent CSV log for strategy setup alerts."""

import csv
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Set, Tuple


IST = timezone(timedelta(hours=5, minutes=30))


class TradeAlertJournal:
    FIELDNAMES = [
        "snapshot_ist",
        "logged_at_ist",
        "symbol",
        "strategy",
        "side",
        "entry_price",
        "stop_loss",
        "target",
        "risk_reward",
        "quantity",
        "confidence",
        "max_risk_inr",
        "potential_reward_inr",
        "rationale",
    ]

    def __init__(self, path: str = "logs/trade_alerts.csv"):
        self.path = path
        self._lock = threading.Lock()
        self._logged_keys: Set[Tuple[str, str, str, str]] = set()
        self._load_logged_keys()

    def _load_logged_keys(self) -> None:
        if not os.path.exists(self.path):
            return

        with open(self.path, "r", newline="", encoding="utf-8") as file:
            for record in csv.DictReader(file):
                self._logged_keys.add(self._key(record))

    @staticmethod
    def _key(record: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
        timestamp = str(record.get("snapshot_ist", record.get("timestamp", "")))
        alert_date = timestamp[:10]
        return (
            alert_date,
            str(record.get("symbol", "")),
            str(record.get("strategy", "")),
            str(record.get("side", "")),
            f"{float(record.get('entry_price', 0.0)):.2f}",
            f"{float(record.get('target', 0.0)):.2f}",
        )

    def log_alert(self, setup: Dict[str, Any]) -> bool:
        """Append each distinct daily setup, including its entry and target."""
        key = self._key(setup)
        with self._lock:
            if key in self._logged_keys:
                return False

            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            file_exists = os.path.exists(self.path) and os.path.getsize(self.path) > 0
            record = {
                "snapshot_ist": setup["timestamp"],
                "logged_at_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": setup["symbol"],
                "strategy": setup["strategy"],
                "side": setup["side"],
                "entry_price": setup["entry_price"],
                "stop_loss": setup["stop_loss"],
                "target": setup["target"],
                "risk_reward": setup["risk_reward"],
                "quantity": setup["quantity"],
                "confidence": setup["confidence"],
                "max_risk_inr": setup["max_risk_inr"],
                "potential_reward_inr": setup["potential_reward_inr"],
                "rationale": setup["rationale"],
            }

            with open(self.path, "a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(record)

            self._logged_keys.add(key)
            return True
