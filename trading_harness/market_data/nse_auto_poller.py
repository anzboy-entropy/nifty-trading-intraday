"""Background NSE polling for the live Streamlit dashboard."""

import logging
import threading
import time
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class NSEAutoPoller:
    def __init__(self, collector: Any, interval_seconds: int = 300):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        self.collector = collector
        self.interval_seconds = interval_seconds
        self._poll_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._next_poll_monotonic: Optional[float] = None
        self._last_poll_at = None
        self._last_result: Optional[Dict[str, Any]] = None

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
                "next_poll_at": self._next_poll_monotonic,
            }

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
            self._next_poll_monotonic = time.monotonic() + self.interval_seconds

        return result

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self.collector.is_market_hours():
                with self._state_lock:
                    self._next_poll_monotonic = None
                self._stop_event.wait(10)
                continue

            with self._poll_lock:
                now = time.monotonic()
                with self._state_lock:
                    next_poll = self._next_poll_monotonic

                if next_poll is None or now >= next_poll:
                    self._perform_poll(force=False)
                    continue

                wait_seconds = min(10, max(0.1, next_poll - now))

            self._stop_event.wait(wait_seconds)
