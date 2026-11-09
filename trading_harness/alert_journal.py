"""Date-partitioned CSV log for strategy setup alerts."""

import csv
import os
import shutil
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


IST = timezone(timedelta(hours=5, minutes=30))


def group_alert_episodes(
    records: List[Dict[str, Any]],
    gap_minutes: int = 15,
) -> List[Dict[str, Any]]:
    """Collapse snapshot-level rows into symbol/direction setup episodes."""
    grouped: Dict[Tuple[str, str], List[Tuple[datetime, Dict[str, Any]]]] = {}
    for record in records:
        timestamp = TradeAlertJournal._parse_timestamp(
            str(record.get("snapshot_ist", record.get("timestamp", "")))
        )
        if timestamp is None:
            continue
        key = (str(record.get("symbol", "")), str(record.get("side", "")))
        grouped.setdefault(key, []).append((timestamp, record))

    episodes = []
    max_gap = timedelta(minutes=gap_minutes)
    for (symbol, side), timestamped_records in grouped.items():
        timestamped_records.sort(key=lambda item: item[0])
        current = []
        for item in timestamped_records:
            if current and item[0] - current[-1][0] > max_gap:
                episodes.append(_summarize_episode(symbol, side, current))
                current = []
            current.append(item)
        if current:
            episodes.append(_summarize_episode(symbol, side, current))

    return sorted(episodes, key=lambda episode: episode["last_seen"], reverse=True)


def _summarize_episode(
    symbol: str,
    side: str,
    timestamped_records: List[Tuple[datetime, Dict[str, Any]]],
) -> Dict[str, Any]:
    latest = dict(timestamped_records[-1][1])
    latest["symbol"] = symbol
    latest["side"] = side
    latest["start_timestamp"] = timestamped_records[0][0].strftime("%Y-%m-%d %H:%M:%S")
    latest["last_seen"] = timestamped_records[-1][0].strftime("%Y-%m-%d %H:%M:%S")
    latest["strategies"] = sorted({
        str(record.get("strategy", ""))
        for _, record in timestamped_records
        if record.get("strategy")
    })
    strategy_rationales = {}
    for _, record in timestamped_records:
        strategy = str(record.get("strategy", ""))
        rationale = str(record.get("rationale", "")).strip()
        if strategy and rationale:
            strategy_rationales[strategy] = rationale
    latest["strategy_rationales"] = strategy_rationales
    latest["rationale"] = " | ".join(
        f"{strategy}: {rationale}"
        for strategy, rationale in sorted(strategy_rationales.items())
    )
    latest["updates"] = len(timestamped_records)
    return latest


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
        self._episode_seen_at: Dict[Tuple[str, str, str, str], datetime] = {}
        self._migrate_legacy_file()
        self._load_episode_timestamps()
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

    def _load_episode_timestamps(self) -> None:
        if not os.path.isdir(self._directory):
            return
        prefixes = (f"{self._stem}_",)
        if self._date_partitioned:
            today = datetime.now(IST).date().isoformat()
            today_filename = f"{self._stem}_{today}.csv"
            paths = [
                path for path in (
                    os.path.join(self._directory, today_filename),
                    os.path.join(self.archive_dir, today_filename),
                )
                if os.path.exists(path)
            ]
        else:
            paths = [self._legacy_path] if os.path.exists(self._legacy_path) else []
            for filename in os.listdir(self._directory):
                if filename.startswith(prefixes) and filename.endswith(".csv"):
                    paths.append(os.path.join(self._directory, filename))
            if os.path.isdir(self.archive_dir):
                for filename in os.listdir(self.archive_dir):
                    if filename.startswith(prefixes) and filename.endswith(".csv"):
                        paths.append(os.path.join(self.archive_dir, filename))

        for path in paths:
            with open(path, "r", newline="", encoding="utf-8") as file:
                for record in csv.DictReader(file):
                    episode_key = self._episode_key(record)
                    timestamp = self._parse_timestamp(
                        record.get("snapshot_ist", record.get("timestamp", ""))
                    )
                    if timestamp is not None and (
                        episode_key not in self._episode_seen_at
                        or timestamp > self._episode_seen_at[episode_key]
                    ):
                        self._episode_seen_at[episode_key] = timestamp

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

    @staticmethod
    def _episode_key(record: Dict[str, Any]) -> Tuple[str, str, str, str]:
        timestamp = str(record.get("snapshot_ist", record.get("timestamp", "")))
        return (
            timestamp[:10],
            str(record.get("symbol", "")),
            str(record.get("strategy", "")),
            str(record.get("side", "")),
        )

    @staticmethod
    def _parse_timestamp(value: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    def log_alert(self, setup: Dict[str, Any]) -> bool:
        """Log an episode start, suppressing price-only repeats within 15 minutes."""
        with self._lock:
            episode_key = self._episode_key(setup)
            date_str = episode_key[0]
            if self._date_partitioned and any(
                key[0] != date_str for key in self._episode_seen_at
            ):
                self._episode_seen_at = {
                    key: timestamp
                    for key, timestamp in self._episode_seen_at.items()
                    if key[0] == date_str
                }
            snapshot_time = self._parse_timestamp(str(setup.get("timestamp", "")))
            if snapshot_time is None:
                raise ValueError(f"Invalid trade-alert timestamp: {setup.get('timestamp')}")
            last_seen = self._episode_seen_at.get(episode_key)
            if last_seen is not None:
                elapsed = snapshot_time - last_seen
                if elapsed <= timedelta(0):
                    return False
                if elapsed <= timedelta(minutes=15):
                    self._episode_seen_at[episode_key] = snapshot_time
                    return False

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

            self._episode_seen_at[episode_key] = snapshot_time
            return True

    def read_alerts(self, date_str: str) -> List[Dict[str, str]]:
        """Read a date's live journal, falling back to its archived file."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"Invalid trade-alert date: {date_str}") from exc

        path = self._path_for_date(date_str) if self._date_partitioned else self._legacy_path
        if self._date_partitioned and not os.path.exists(path):
            path = os.path.join(self.archive_dir, f"{self._stem}_{date_str}.csv")
        if not os.path.exists(path):
            return []
        with open(path, "r", newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

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
