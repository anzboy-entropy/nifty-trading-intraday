"""Date-partitioned CSV log for strategy setup alerts."""

import csv
import os
import shutil
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple


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

    def __init__(
        self,
        path: Optional[str] = None,
        archive_dir: Optional[str] = None,
        date_partitioned: Optional[bool] = None,
    ):
        self._legacy_path = path or "logs/trade_alerts.csv"
        self._date_partitioned = path is None if date_partitioned is None else date_partitioned
        self._directory = os.path.dirname(self._legacy_path) or "."
        self._stem = os.path.splitext(os.path.basename(self._legacy_path))[0]
        self.archive_dir = archive_dir or os.path.join(self._directory, "archive")
        self._lock = threading.Lock()
        self._logged_keys: Set[Tuple[str, str, str, str, str, str]] = set()
        self._migrate_legacy_file()
        self._load_logged_keys()
        if self._date_partitioned:
            self.archive_expired_files()

    @property
    def path(self) -> str:
        if not self._date_partitioned:
            return self._legacy_path
        return self._path_for_date(datetime.now(IST).date().isoformat())

    def _path_for_date(self, date_str: str) -> str:
        return os.path.join(self._directory, f"{self._stem}_{date_str}.csv")

    def _migrate_legacy_file(self) -> None:
        if not self._date_partitioned or not os.path.exists(self._legacy_path):
            return
        grouped_records: Dict[str, List[Dict[str, Any]]] = {}
        with open(self._legacy_path, "r", newline="", encoding="utf-8") as file:
            for record in csv.DictReader(file):
                snapshot_date = str(record.get("snapshot_ist", ""))[:10]
                try:
                    datetime.strptime(snapshot_date, "%Y-%m-%d")
                except ValueError as exc:
                    raise ValueError(
                        f"Cannot migrate trade alert with invalid timestamp: "
                        f"{record.get('snapshot_ist')}"
                    ) from exc
                grouped_records.setdefault(snapshot_date, []).append(record)
        if not grouped_records:
            raise ValueError(f"Legacy trade journal contains no dated rows: {self._legacy_path}")

        os.makedirs(self._directory, exist_ok=True)
        for date_str, records in grouped_records.items():
            path = self._path_for_date(date_str)
            existing_keys = set()
            if os.path.exists(path):
                with open(path, "r", newline="", encoding="utf-8") as file:
                    existing_keys = {self._key(row) for row in csv.DictReader(file)}
            file_exists = os.path.exists(path) and os.path.getsize(path) > 0
            with open(path, "a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                for record in records:
                    if self._key(record) not in existing_keys:
                        writer.writerow(record)
                        existing_keys.add(self._key(record))
        os.remove(self._legacy_path)

    def _load_logged_keys(self) -> None:
        if not os.path.isdir(self._directory):
            return
        prefixes = (f"{self._stem}_",)
        paths = [self._legacy_path] if not self._date_partitioned and os.path.exists(self._legacy_path) else []
        for filename in os.listdir(self._directory):
            if filename.startswith(prefixes) and filename.endswith(".csv"):
                paths.append(os.path.join(self._directory, filename))
        if os.path.isdir(self.archive_dir):
            for filename in os.listdir(self.archive_dir):
                if filename.startswith(prefixes) and filename.endswith(".csv"):
                    paths.append(os.path.join(self.archive_dir, filename))
        for path in paths:
            with open(path, "r", newline="", encoding="utf-8") as file:
                self._logged_keys.update(self._key(record) for record in csv.DictReader(file))

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
        """Append each distinct setup to its snapshot-date journal."""
        key = self._key(setup)
        with self._lock:
            if key in self._logged_keys:
                return False

            date_str = key[0]
            try:
                snapshot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError(f"Invalid trade-alert timestamp: {setup.get('timestamp')}") from exc
            now = datetime.now(IST)
            archive = self._date_partitioned and (
                snapshot_date < now.date()
                or (
                    snapshot_date == now.date()
                    and now.time() >= datetime.strptime("15:30", "%H:%M").time()
                )
            )
            path = self._path_for_date(date_str) if self._date_partitioned else self._legacy_path
            if archive:
                path = os.path.join(self.archive_dir, f"{self._stem}_{date_str}.csv")
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            file_exists = os.path.exists(path) and os.path.getsize(path) > 0
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

            with open(path, "a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(record)

            self._logged_keys.add(key)
            return True

    def archive_expired_files(
        self,
        now: Optional[datetime] = None,
        include_current: bool = False,
    ) -> List[str]:
        """Move completed date-partitioned journals to logs/archive."""
        if not self._date_partitioned or not os.path.isdir(self._directory):
            return []
        now = now or datetime.now(IST)
        archived = []
        for filename in os.listdir(self._directory):
            if not filename.startswith(f"{self._stem}_") or not filename.endswith(".csv"):
                continue
            date_str = filename[len(self._stem) + 1:-4]
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            is_expired = file_date < now.date() or (
                include_current and file_date == now.date()
            )
            if not is_expired:
                continue
            source = os.path.join(self._directory, filename)
            target = os.path.join(self.archive_dir, filename)
            os.makedirs(self.archive_dir, exist_ok=True)
            if os.path.exists(target):
                self._merge_journal_files(target, source)
                os.remove(source)
            else:
                shutil.move(source, target)
            archived.append(target)
        return archived

    def _merge_journal_files(self, archive_path: str, daily_path: str) -> None:
        with open(archive_path, "r", newline="", encoding="utf-8") as file:
            existing_keys = {self._key(record) for record in csv.DictReader(file)}
        with open(daily_path, "r", newline="", encoding="utf-8") as file:
            additions = [
                record for record in csv.DictReader(file)
                if self._key(record) not in existing_keys
            ]
        if additions:
            with open(archive_path, "a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
                writer.writerows(additions)
