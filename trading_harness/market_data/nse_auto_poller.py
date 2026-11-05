"""Background NSE polling for the live Streamlit dashboard."""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


class NSEAutoPoller:
    def __init__(
        self,
        collector: Any,
        interval_seconds: int = 300,
        maintenance_callbacks: Optional[List[Callable[[], Any]]] = None,
    ):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        self.collector = collector
        self.interval_seconds = interval_seconds
        self.maintenance_callbacks = maintenance_callbacks or []
        self._poll_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._next_poll_at: Optional[datetime] = None
        self._last_poll_at = None
        self._last_result: Optional[Dict[str, Any]] = None
        self._last_maintenance_monotonic = 0.0

    def start(self) -> None:
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="nse-auto-poller",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def poll_now(self, force: bool = True) -> Dict[str, Any]:
        with self._poll_lock:
            return self._perform_poll(force)

    def archive_now(self):
        with self._poll_lock:
            return self.collector.archive_running_file()

    def get_status(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "last_poll_at": self._last_poll_at,
                "last_result": dict(self._last_result) if self._last_result else None,
                "next_poll_at": self._next_poll_at,
            }

    def _next_aligned_poll(self, now: datetime) -> datetime:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_today = (now - day_start).total_seconds()
        next_interval = (int(seconds_today // self.interval_seconds) + 1) * self.interval_seconds
        return day_start + timedelta(seconds=next_interval)

    def _perform_poll(self, force: bool) -> Dict[str, Any]:
        try:
            result = self.collector.run_single_cycle(force=force)
        except Exception as exc:
            logger.exception("Automatic NSE snapshot poll failed")
            result = {
                "status": "ERROR",
                "time_ist": self.collector.get_ist_now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(exc),
            }

        with self._state_lock:
            self._last_poll_at = self.collector.get_ist_now()
            self._last_result = dict(result)

        return result

    def _run(self) -> None:
        while not self._stop_event.is_set():
            now_monotonic = time.monotonic()
            if now_monotonic - self._last_maintenance_monotonic >= 60:
                try:
                    self.collector.check_and_perform_eod_archive()
                except Exception:
                    logger.exception("Daily snapshot archive maintenance failed")
                for callback in self.maintenance_callbacks:
                    try:
                        callback()
                    except Exception:
                        logger.exception("Daily trade-call archive maintenance failed")
                self._last_maintenance_monotonic = now_monotonic

            if not self.collector.is_market_hours():
                with self._state_lock:
                    self._next_poll_at = None
                self._stop_event.wait(10)
                continue

            now = self.collector.get_ist_now()
            with self._state_lock:
                if self._next_poll_at is None:
                    self._next_poll_at = self._next_aligned_poll(now)
                next_poll_at = self._next_poll_at

            wait_seconds = (next_poll_at - now).total_seconds()
            if wait_seconds > 0:
                self._stop_event.wait(min(1, wait_seconds))
                continue

            with self._poll_lock:
                self._perform_poll(force=False)
                with self._state_lock:
                    self._next_poll_at = self._next_aligned_poll(
                        self.collector.get_ist_now()
                    )
