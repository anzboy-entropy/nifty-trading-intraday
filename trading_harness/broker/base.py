"""
Abstract Base Broker interface for Indian Intraday Trading.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseBroker(ABC):
    @abstractmethod
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Places a new order with the broker"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancels an existing pending order"""
        pass

    @abstractmethod
    def modify_order(self, order_id: str, new_price: Optional[float] = None, 
                     new_quantity: Optional[int] = None, new_trigger_price: Optional[float] = None) -> Dict[str, Any]:
        """Modifies price, quantity or stop loss trigger of a pending order"""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Returns all open and closed intraday positions"""
        pass

    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Returns order book for the day"""
        pass

    @abstractmethod
    def get_ltp(self, symbol: str) -> float:
        """Returns last traded price for symbol"""
        pass

    @abstractmethod
    def square_off_all(self, reason: str = "MANUAL") -> List[Dict[str, Any]]:
        """Closes all open intraday positions immediately"""
        pass
