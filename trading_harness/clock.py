"""
Market Clock for Indian Markets (IST).
Handles session phases, volatility windows, and mandatory MIS square-off timings.
"""

from datetime import datetime, time, timezone, timedelta
from typing import Optional
from .config import MarketSessionConfig

# Indian Standard Time is UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

class IndianMarketClock:
    def __init__(self, session_config: Optional[MarketSessionConfig] = None, simulated_time: Optional[datetime] = None):
        self.config = session_config or MarketSessionConfig()
        self.simulated_time = simulated_time

    def set_simulated_time(self, sim_time: datetime):
        """Set custom clock for backtesting or simulation"""
        self.simulated_time = sim_time

    def now(self) -> datetime:
        """Returns current IST datetime (or simulated IST datetime)"""
        if self.simulated_time is not None:
            return self.simulated_time
        return datetime.now(IST)

    def current_time_str(self) -> str:
        """Returns HH:MM format in IST"""
        return self.now().strftime("%H:%M")

    def _parse_time(self, time_str: str) -> time:
        parts = [int(p) for p in time_str.split(":")]
        return time(parts[0], parts[1])

    def is_market_open(self) -> bool:
        """Checks if current time is within active trading hours (09:15 to 15:30 IST) on weekdays"""
        current_dt = self.now()
        if current_dt.weekday() >= 5: # Saturday or Sunday
            return False
        
        t = current_dt.time()
        start = self._parse_time(self.config.market_open)
        end = self._parse_time(self.config.market_close)
        return start <= t <= end

    def is_pre_market(self) -> bool:
        """Checks if current time is within Pre-Open discovery window (09:00 - 09:08)"""
        current_dt = self.now()
        t = current_dt.time()
        start = self._parse_time(self.config.pre_open_start)
        end = self._parse_time(self.config.pre_open_end)
        return start <= t <= end

    def is_square_off_time(self) -> bool:
        """Checks if it's 15:20 IST or later - mandatory square-off period"""
        current_dt = self.now()
        t = current_dt.time()
        sq_time = self._parse_time(self.config.auto_square_off_time)
        return t >= sq_time

    def get_session_phase(self) -> str:
        """
        Returns the active Indian market session phase:
        - PRE_OPEN: 09:00 - 09:08
        - BUFFER: 09:08 - 09:15
        - MORNING_VOLATILITY: 09:15 - 10:15
        - PRIMARY_BREAKOUT: 10:15 - 11:30
        - MIDDAY_CONSOLIDATION: 11:30 - 13:30
        - AFTERNOON_SESSION: 13:30 - 14:30
        - SQUARE_OFF_HOUR: 14:30 - 15:20
        - MANDATORY_SQUARE_OFF: 15:20 - 15:30
        - CLOSED: After 15:30 or before 09:00
        """
        t = self.now().time()
        
        if t < self._parse_time(self.config.pre_open_start):
            return "CLOSED"
        elif t <= self._parse_time(self.config.pre_open_end):
            return "PRE_OPEN"
        elif t < self._parse_time(self.config.market_open):
            return "BUFFER"
        elif t <= self._parse_time(self.config.volatility_hour_end):
            return "MORNING_VOLATILITY"
        elif t < self._parse_time(self.config.midday_start):
            return "PRIMARY_BREAKOUT"
        elif t <= self._parse_time(self.config.midday_end):
            return "MIDDAY_CONSOLIDATION"
        elif t < self._parse_time(self.config.closing_hour_start):
            return "AFTERNOON_SESSION"
        elif t < self._parse_time(self.config.auto_square_off_time):
            return "SQUARE_OFF_HOUR"
        elif t <= self._parse_time(self.config.market_close):
            return "MANDATORY_SQUARE_OFF"
        else:
            return "CLOSED"
