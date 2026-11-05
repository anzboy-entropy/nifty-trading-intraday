"""
CLI Entrypoint for NSE Live NIFTY 50 Collector.
Usage:
  python run_nse_collector.py                     # Runs continuous 3-minute loop
  python run_nse_collector.py --once --force       # Fetches 1 snapshot now (even off-market)
  python run_nse_collector.py --archive-now        # Archives running file to data/archive/
  python run_nse_collector.py --status             # Displays running file status
"""

import sys
import argparse
import os
import json
from trading_harness.market_data.nse_live_collector import NSELiveCollector

def main():
    parser = argparse.ArgumentParser(description="NSE Live 3-minute NIFTY 50 Collector & Archiver")
    parser.add_argument("--interval", type=int, default=180, help="Interval in seconds (default: 180 = 3 mins)")
    parser.add_argument("--once", action="store_true", help="Fetch a single 3-minute snapshot and exit")
    parser.add_argument("--force", action="store_true", help="Force fetch even outside active market hours")
    parser.add_argument("--archive-now", action="store_true", help="Archive current running file to data/archive/")
    parser.add_argument("--status", action="store_true", help="Show current live running file status")
    
    args = parser.parse_args()
    collector = NSELiveCollector()

    if args.status:
        running_path = collector.running_file_path
        latest_path = collector.latest_json_path
        
        print("=== NSE LIVE COLLECTOR STATUS ===")
        print(f"Current IST Time: {collector.get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Market Active:    {collector.is_market_hours()}")
        print(f"Running File:     {running_path} (Exists: {os.path.exists(running_path)})")
        
        if os.path.exists(running_path):
            size_kb = os.path.getsize(running_path) / 1024.0
            with open(running_path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f) - 1 # Subtract header
            snapshots = max(0, lines // 51)
            print(f"Running File Size: {size_kb:.1f} KB | Total Rows: {lines} (~{snapshots} snapshots)")

        if os.path.exists(latest_path):
            with open(latest_path, "r", encoding="utf-8") as jf:
                info = json.load(jf)
            idx = info.get("index", {})
            print(f"Latest Snapshot:  {info.get('last_updated_ist')}")
            print(f"NIFTY 50 Index:   LTP {idx.get('last_price')} | Change: {idx.get('p_change'):+0.2f}%")
            print(f"Constituents:     {info.get('total_constituents')} stocks tracked")

        return

    if args.archive_now:
        archived = collector.archive_running_file()
        if archived:
            print(f"[SUCCESS] Archived running file to: {archived}")
        else:
            print("[INFO] No running file found or file is empty.")
        return

    if args.once:
        print("[INFO] Executing single snapshot fetch...")
        res = collector.run_single_cycle(force=args.force)
        print(json.dumps(res, indent=2))
        return

    # Default: Continuous 3-minute loop
    collector.start_continuous_loop(interval_seconds=args.interval, force=args.force)

if __name__ == "__main__":
    main()
