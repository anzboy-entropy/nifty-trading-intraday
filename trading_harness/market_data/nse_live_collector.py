"""
NSE Live Data Collector for NIFTY 50 Index and Constituent Stocks.
Fetches real-time market data every 3 minutes, appends to a running intraday file,
and automatically archives to an EOD archive file at market close (15:30 IST).
"""

import os
import sys
import time
import json
import csv
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

try:
    from curl_cffi import requests
except ImportError:
    requests = None

# Indian Standard Time (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))

CSV_HEADERS = [
    "snapshot_ist",
    "symbol",
    "is_index",
    "company_name",
    "last_price",
    "change",
    "p_change",
    "open",
    "day_high",
    "day_low",
    "prev_close",
    "volume",
    "total_traded_value",
    "year_high",
    "year_low",
    "nse_timestamp"
]

class NSELiveCollector:
    """
    Robust scraper and archiver for NSE India NIFTY 50 and constituent stocks.
    Uses browser TLS impersonation to bypass Akamai bot protection.
    """
    BASE_URL = "https://www.nseindia.com"
    API_URL = "https://www.nseindia.com/api/NextApi/apiClient/marketWatchApi?functionName=getIndicesData&symbol=NIFTY%2050"

    def __init__(
        self,
        live_dir: str = "data/live",
        archive_dir: str = "data/archive",
        running_filename: str = "nifty50_running.csv",
        latest_json_filename: str = "nifty50_latest.json"
    ):
        self.live_dir = live_dir
        self.archive_dir = archive_dir
        self.running_file_prefix = running_filename.replace("_running.csv", "")
        self.legacy_running_file_path = os.path.join(live_dir, running_filename)
        self.latest_json_path = os.path.join(live_dir, latest_json_filename)
        
        self.session: Optional[Any] = None
        self.session_initialized_at: Optional[datetime] = None
        self.last_archived_date: Optional[str] = None
        
        self._ensure_directories()
        self._migrate_legacy_running_file()
        self.check_and_perform_eod_archive()
        self._restore_archived_file(self.get_ist_now().date().isoformat())

    @property
    def running_file_path(self) -> str:
        return self.daily_file_path(self.get_ist_now().date().isoformat())

    def daily_file_path(self, date_str: str) -> str:
        return os.path.join(
            self.live_dir,
            f"{self.running_file_prefix}_{date_str}.csv",
        )

    def _ensure_directories(self):
        os.makedirs(self.live_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

    def get_ist_now(self) -> datetime:
        return datetime.now(IST)

    def is_market_hours(self, dt: Optional[datetime] = None) -> bool:
        """
        NSE trading hours: 09:15 AM to 03:30 PM IST, Monday to Friday.
        """
        now = dt or self.get_ist_now()
        if now.weekday() >= 5: # Saturday = 5, Sunday = 6
            return False
        
        current_time = now.time()
        market_open = datetime.strptime("09:15", "%H:%M").time()
        market_close = datetime.strptime("15:30", "%H:%M").time()
        
        return market_open <= current_time <= market_close

    def init_session(self) -> bool:
        """
        Initializes curl_cffi session impersonating Chrome 120,
        visiting NSE homepage to acquire essential cookies.
        """
        if requests is None:
            raise RuntimeError("curl_cffi is required to fetch data from NSE. Please install it.")

        try:
            self.session = requests.Session(impersonate="chrome120")
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = self.session.get(self.BASE_URL, headers=headers, verify=False, timeout=15)
            if resp.status_code == 200:
                self.session_initialized_at = self.get_ist_now()
                return True
        except Exception as e:
            print(f"[NSELiveCollector] Session Init Failed: {e}")
        return False

    def fetch_snapshot(self, retries: int = 2) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Fetches the NIFTY 50 Index + all 50 constituent stocks from NSE.
        Returns: (success, records_list, nse_timestamp_str)
        """
        if self.session is None:
            if not self.init_session():
                return False, [], "Session init failed"

        headers = {
            "Referer": "https://www.nseindia.com/market-data/live-equity-market",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest"
        }
        last_error = "NSE did not return a response"

        for attempt in range(retries + 1):
            try:
                resp = self.session.get(self.API_URL, headers=headers, verify=False, timeout=15)

                if resp.status_code != 200:
                    response_hint = " ".join((getattr(resp, "text", "") or "").split())[:160]
                    last_error = f"NSE returned HTTP {resp.status_code}"
                    if response_hint:
                        last_error = f"{last_error}: {response_hint}"

                    retryable = (
                        resp.status_code in (401, 403, 429)
                        or resp.status_code >= 500
                    )
                    if resp.status_code in (401, 403) and attempt < retries:
                        self.init_session()
                    if not retryable or attempt == retries:
                        return False, [], last_error
                    time.sleep(min(2 ** attempt, 8))
                    continue

                raw_data = resp.json()
                data_container = raw_data.get("data", {})
                items = data_container.get("data", [])
                nse_time = data_container.get("timestamp", "")

                if not items:
                    return False, [], "NSE response contained no market data"

                snapshot_time = self.get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
                parsed_records = []

                for idx, item in enumerate(items):
                    is_index = (idx == 0) or (item.get("symbol") == "NIFTY 50")
                    rec = {
                        "snapshot_ist": snapshot_time,
                        "symbol": item.get("symbol"),
                        "is_index": is_index,
                        "company_name": item.get("companyName", "NIFTY 50 INDEX" if is_index else ""),
                        "last_price": float(item.get("lastPrice", 0.0) or 0.0),
                        "change": float(item.get("change", 0.0) or 0.0),
                        "p_change": float(item.get("pChange", 0.0) or 0.0),
                        "open": float(item.get("open", 0.0) or 0.0),
                        "day_high": float(item.get("dayHigh", 0.0) or 0.0),
                        "day_low": float(item.get("dayLow", 0.0) or 0.0),
                        "prev_close": float(item.get("previousClose", 0.0) or 0.0),
                        "volume": int(item.get("totalTradedVolume", 0) or 0),
                        "total_traded_value": float(item.get("totalTradedValue", 0.0) or 0.0),
                        "year_high": float(item.get("yearHigh", 0.0) or 0.0),
                        "year_low": float(item.get("yearLow", 0.0) or 0.0),
                        "nse_timestamp": item.get("lastUpdateTime") or nse_time
                    }
                    parsed_records.append(rec)

                return True, parsed_records, nse_time

            except Exception as e:
                last_error = f"NSE request failed: {e}"
                if attempt == retries:
                    return False, [], last_error
                time.sleep(min(2 ** attempt, 8))
                self.init_session()

        return False, [], last_error

    def append_to_running_file(self, records: List[Dict[str, Any]]):
        """
        Appends a snapshot to its date-specific live CSV file,
        and saves the latest snapshot to JSON for instant query access.
        """
        if not records:
            return
        snapshot_dates = {str(record["snapshot_ist"])[:10] for record in records}
        if len(snapshot_dates) != 1:
            raise ValueError("A snapshot batch must contain exactly one trading date")
        date_tag = snapshot_dates.pop()
        try:
            datetime.strptime(date_tag, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"Invalid snapshot date: {date_tag}") from exc
        self._restore_archived_file(date_tag)
        daily_path = self.daily_file_path(date_tag)
        file_exists = os.path.exists(daily_path) and os.path.getsize(daily_path) > 0

        with open(daily_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if not file_exists:
                writer.writeheader()
            for r in records:
                writer.writerow(r)

        # Also update nifty50_latest.json
        index_data = records[0] if records else {}
        stocks_dict = {r["symbol"]: r for r in records[1:]}
        
        latest_payload = {
            "last_updated_ist": self.get_ist_now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_constituents": len(stocks_dict),
            "index": index_data,
            "stocks": stocks_dict
        }
        
        with open(self.latest_json_path, "w", encoding="utf-8") as jf:
            json.dump(latest_payload, jf, indent=2)

    def archive_running_file(self, target_date_str: Optional[str] = None) -> Optional[str]:
        """
        Moves one date-specific snapshot file to the archive directory.
        """
        date_tag = target_date_str or self.get_ist_now().strftime("%Y-%m-%d")
        running_path = self.daily_file_path(date_tag)
        if not os.path.exists(running_path) or os.path.getsize(running_path) == 0:
            return None

        archived_path = os.path.join(
            self.archive_dir,
            f"{self.running_file_prefix}_{date_tag}.csv",
        )
        if os.path.exists(archived_path):
            self._merge_snapshot_files(archived_path, running_path)
            os.remove(running_path)
        else:
            shutil.move(running_path, archived_path)
        self.last_archived_date = date_tag
        print(f"[NSELiveCollector] [ARCHIVE] Moved running file to: {archived_path}")
        return archived_path

    def _restore_archived_file(self, date_tag: str) -> Optional[str]:
        """Restore a date's archive to live storage, merging any split live rows."""
        archived_path = os.path.join(
            self.archive_dir,
            f"{self.running_file_prefix}_{date_tag}.csv",
        )
        daily_path = self.daily_file_path(date_tag)
        if not os.path.exists(archived_path):
            return None

        if os.path.exists(daily_path):
            self._merge_snapshot_files(daily_path, archived_path)
            os.remove(archived_path)
        else:
            shutil.move(archived_path, daily_path)
        print(f"[NSELiveCollector] [RESTORE] Recovered daily file: {daily_path}")
        return daily_path

    @staticmethod
    def _merge_snapshot_files(destination_path: str, source_path: str) -> None:
        """Merge chronologically, preserving one row per snapshot timestamp and symbol."""
        with open(destination_path, "r", newline="", encoding="utf-8") as destination_file:
            records = {
                (row.get("snapshot_ist", ""), row.get("symbol", "")): row
                for row in csv.DictReader(destination_file)
            }
        original_count = len(records)
        with open(source_path, "r", newline="", encoding="utf-8") as source_file:
            for row in csv.DictReader(source_file):
                key = (row.get("snapshot_ist", ""), row.get("symbol", ""))
                records.setdefault(key, row)
        if len(records) > original_count:
            ordered_records = sorted(
                records.values(),
                key=lambda row: (row.get("snapshot_ist", ""), row.get("symbol", "")),
            )
            descriptor, temp_path = tempfile.mkstemp(
                prefix=".snapshot-merge-",
                suffix=".csv",
                dir=os.path.dirname(destination_path) or ".",
            )
            try:
                with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as destination_file:
                    writer = csv.DictWriter(destination_file, fieldnames=CSV_HEADERS)
                    writer.writeheader()
                    writer.writerows(ordered_records)
                os.replace(temp_path, destination_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    def _migrate_legacy_running_file(self) -> None:
        if not os.path.exists(self.legacy_running_file_path):
            return
        if os.path.getsize(self.legacy_running_file_path) == 0:
            os.remove(self.legacy_running_file_path)
            return
        grouped_records: Dict[str, List[Dict[str, Any]]] = {}
        with open(self.legacy_running_file_path, "r", newline="", encoding="utf-8") as legacy_file:
            for record in csv.DictReader(legacy_file):
                snapshot_date = str(record.get("snapshot_ist", ""))[:10]
                try:
                    datetime.strptime(snapshot_date, "%Y-%m-%d")
                except ValueError:
                    raise ValueError(
                        f"Cannot migrate snapshot with invalid timestamp: {record.get('snapshot_ist')}"
                    )
                grouped_records.setdefault(snapshot_date, []).append(record)

        if not grouped_records:
            os.remove(self.legacy_running_file_path)
            return
        for date_tag, records in grouped_records.items():
            daily_path = self.daily_file_path(date_tag)
            if os.path.exists(daily_path):
                temp_path = self._write_temp_snapshot(records)
                try:
                    self._merge_snapshot_files(daily_path, temp_path)
                finally:
                    os.remove(temp_path)
            else:
                with open(daily_path, "w", newline="", encoding="utf-8") as daily_file:
                    writer = csv.DictWriter(daily_file, fieldnames=CSV_HEADERS)
                    writer.writeheader()
                    writer.writerows(records)
        os.remove(self.legacy_running_file_path)

    def _write_temp_snapshot(self, records: List[Dict[str, Any]]) -> str:
        temp_path = os.path.join(self.live_dir, f".{self.running_file_prefix}_migration.csv")
        with open(temp_path, "w", newline="", encoding="utf-8") as temp_file:
            writer = csv.DictWriter(temp_file, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(records)
        return temp_path

    def archive_expired_files(self, now: Optional[datetime] = None) -> List[str]:
        now = now or self.get_ist_now()
        archived = []
        for filename in os.listdir(self.live_dir):
            if not filename.startswith(f"{self.running_file_prefix}_") or not filename.endswith(".csv"):
                continue
            date_tag = filename[len(self.running_file_prefix) + 1:-4]
            try:
                file_date = datetime.strptime(date_tag, "%Y-%m-%d").date()
            except ValueError:
                continue
            if file_date < now.date():
                result = self.archive_running_file(date_tag)
                if result:
                    archived.append(result)
        return archived

    def check_and_perform_eod_archive(self):
        """
        Archives completed trading-day files, including days missed while offline.
        """
        return self.archive_expired_files()

    def run_single_cycle(self, force: bool = False) -> Dict[str, Any]:
        """
        Executes a single 3-minute poll cycle.
        """
        now = self.get_ist_now()
        is_open = self.is_market_hours(now)
        
        if not is_open and not force:
            self.check_and_perform_eod_archive()
            return {
                "status": "MARKET_CLOSED",
                "time_ist": now.strftime("%Y-%m-%d %H:%M:%S"),
                "message": "Market is closed. Running file archived or standby."
            }

        success, records, nse_time = self.fetch_snapshot()
        if success:
            self.append_to_running_file(records)
            idx_rec = records[0]
            print(f"[{now.strftime('%H:%M:%S')} IST] Collected {len(records)} items | NIFTY 50: {idx_rec['last_price']} ({idx_rec['p_change']:+0.2f}%)")
            
            # Post-fetch EOD check
            if not is_open and force:
                pass
            else:
                self.check_and_perform_eod_archive()

            return {
                "status": "SUCCESS",
                "time_ist": now.strftime("%Y-%m-%d %H:%M:%S"),
                "nse_timestamp": nse_time,
                "total_records": len(records),
                "nifty_index": idx_rec
            }
        else:
            print(f"[{now.strftime('%H:%M:%S')} IST] Fetch failed: {nse_time}")
            return {
                "status": "ERROR",
                "time_ist": now.strftime("%Y-%m-%d %H:%M:%S"),
                "error": nse_time
            }

    def start_continuous_loop(self, interval_seconds: int = 180, force: bool = False):
        """
        Runs continuously every 3 minutes (180s default).
        During market hours, appends to running file.
        At 15:30 IST, archives to EOD file.
        """
        print("=" * 75)
        print("NSE LIVE NIFTY 50 DATA COLLECTOR (3-MINUTE CADENCE)")
        print(f"Running File: {self.running_file_path}")
        print(f"Archive Dir:  {self.archive_dir}")
        print(f"Interval:     {interval_seconds} seconds (3 minutes)")
        print(f"Force Mode:   {force} (runs outside 09:15-15:30 IST if True)")
        print("=" * 75)

        try:
            while True:
                self.run_single_cycle(force=force)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n[NSELiveCollector] Stopped by user.")
