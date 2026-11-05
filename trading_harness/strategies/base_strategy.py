"""
Base Strategy Interface for Indian Intraday Trading.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseStrategy(ABC):
    def __init__(self, name: str, timeframe: str = "5m"):
        self.name = name
        self.timeframe = timeframe

    @abstractmethod
    def evaluate(self, symbol: str, market_data: Any, clock: Any) -> Optional[Dict[str, Any]]:
        """
        Evaluates market conditions for a symbol and returns a trade signal if conditions are satisfied.
        Signal format:
        {
            "strategy": self.name,
            "symbol": symbol,
            "side": "BUY" | "SELL",
            "entry_price": float,
            "stop_loss": float,
            "target": float,
            "product": "MIS",
            "rationale": str
        }
        Returns None if no setup is present.
        """
        pass
